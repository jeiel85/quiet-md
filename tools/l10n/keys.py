#!/usr/bin/env python3
"""List the UI strings a translation in src/l10n/ needs, as JSON: one entry
per Chinese key with its English text and where it is used.

    python3 tools/l10n/keys.py            # every key
    python3 tools/l10n/keys.py --missing ko   # keys src/l10n/ko.rs lacks

Sources: the zh -> en `localize` table and diagnostic templates in
src/settings.rs, `tr("…", "…")`, `localized_format!("…", "…")`, and
("…", "…") pair tables (shortcuts, changelog of the running version, menus).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIT = r'"((?:[^"\\]|\\.)*)"'
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')


def unescape(s):
    return re.sub(r'\\(u\{[0-9a-fA-F]+\}|.)', lambda m: chr(int(m[1][2:-1], 16)) if m[1].startswith('u{') else {'n': '\n', 't': '\t'}.get(m[1], m[1]), s)


def version():
    return re.search(r'^version = "([^"]+)"', (ROOT / 'Cargo.toml').read_text(encoding='utf-8'), re.M)[1]


def collect():
    keys = {}

    def add(zh, en, kind, where):
        zh, en = unescape(zh), unescape(en)
        if not CJK.search(zh):
            return
        e = keys.setdefault(zh, {'zh': zh, 'en': [], 'kinds': [], 'at': []})
        if en not in e['en']: e['en'].append(en)
        if kind not in e['kinds']: e['kinds'].append(kind)
        if len(e['at']) < 3: e['at'].append(where)

    for path in sorted((ROOT / 'src').rglob('*.rs')):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('src/l10n/'):
            continue
        text = path.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        line = lambda pos: f'{rel}:{text.count(chr(10), 0, pos) + 1}'
        if rel == 'src/changelog.rs':
            # Only the running version's notes are ever shown.
            m = re.search(r'\("' + re.escape(version()) + r'", &\[(.*?)\n    \]\),', text, re.S)
            for p in re.finditer(r'\(' + LIT + r',\s*' + LIT + r'\)', m[1] if m else ''):
                add(p[1], p[2], 'changelog', line(m.start(1) + p.start()))
            # The other versions' notes are not keys; keep the line numbers of what follows.
            notes = re.search(r'const NOTES: .*?\n\];', text, re.S)
            if notes: text = text[:notes.start()] + '\n' * notes[0].count('\n') + text[notes.end():]
        for m in re.finditer(LIT + r'\s*=>\s*' + LIT, text):
            add(m[1], m[2], 'table', line(m.start()))
        for m in re.finditer(r'\btr\(\s*' + LIT + r'\s*,\s*' + LIT, text):
            add(m[1], m[2], 'tr', line(m.start()))
        for m in re.finditer(r'localized_format!\(\s*' + LIT + r'\s*,\s*' + LIT, text):
            add(m[1], m[2], 'format', line(m.start()))
        # Pair tables: ("中文", "English") or (group, "中文", "English").
        for m in re.finditer(r'\(\s*(?:[^(),"]+,\s*)?' + LIT + r'\s*,\s*' + LIT + r'\s*[,)]', text):
            if CJK.search(unescape(m[1])) and not CJK.search(unescape(m[2])):
                add(m[1], m[2], 'pair', line(m.start()))
    return keys


def translated(lang):
    text = (ROOT / 'src/l10n' / f'{lang}.rs').read_text(encoding='utf-8')
    return {unescape(m[1]) for m in re.finditer(r'\(\s*' + LIT + r'\s*,\s*' + LIT + r'\s*\)', text)}


if __name__ == '__main__':
    keys = collect()
    if len(sys.argv) == 3 and sys.argv[1] == '--missing':
        have = translated(sys.argv[2])
        keys = {k: v for k, v in keys.items() if k not in have}
    sys.stdout.reconfigure(encoding="utf-8")
    json.dump(list(keys.values()), sys.stdout, ensure_ascii=False, indent=1)
    print(f'\n{len(keys)} keys', file=sys.stderr)
