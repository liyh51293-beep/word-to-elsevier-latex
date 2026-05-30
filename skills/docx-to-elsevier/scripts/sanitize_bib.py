"""Sanitize refs.bib: replace non-ASCII with LaTeX-safe equivalents."""
import pathlib, re, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PAPER_OUT
BIB = PAPER_OUT / 'refs.bib'
txt = BIB.read_text(encoding='utf-8')

# Latin diacritics -> TeX accent macros
LATIN = {
    'ö':r'\"{o}', 'ü':r'\"{u}', 'ä':r'\"{a}',
    'Ö':r'\"{O}', 'Ü':r'\"{U}', 'Ä':r'\"{A}',
    'é':r"\'{e}", 'á':r"\'{a}", 'í':r"\'{i}", 'ó':r"\'{o}", 'ú':r"\'{u}",
    'É':r"\'{E}", 'Á':r"\'{A}",
    'è':r'\`{e}', 'à':r'\`{a}',
    'ê':r'\^{e}', 'â':r'\^{a}',
    'ñ':r'\~{n}', 'ã':r'\~{a}',
    'ç':r'\c{c}', 'Ç':r'\c{C}',
    'š':r'\v{s}', 'ž':r'\v{z}', 'č':r'\v{c}',
    'Š':r'\v{S}', 'Ž':r'\v{Z}', 'Č':r'\v{C}',
    'ė':r'\.{e}', 'ż':r'\.{z}',
    'ł':r'\l{}', 'ø':r'\o{}', 'å':r'\r{a}', 'Å':r'\r{A}', 'ß':r'\ss{}',
    'ū':r'\={u}', 'ī':r'\={i}', 'ā':r'\={a}',
    'ą':r'\k{a}', 'ę':r'\k{e}',
    'ﬁ':'fi', 'ﬂ':'fl',
    '‐':'-',  # hyphen
    '–':'--', '—':'---',
    'µ':r'$\mu$', 'μ':r'$\mu$',
    '′':"'", '″':"''",
    '×':r'$\times$', '°':r'$^{\circ}$',
    '­':'',  # soft hyphen
    '​':'',  # ZWSP
    ' ':'~',
    '"':"''", '"':'``',  # smart quotes
    "'":"'", "'":'`',
}

# Korean journal name transliteration (line-by-line in original bib)
# Replace whole journal field values containing Hangul.
def is_hangul(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3 or 0x1100 <= ord(ch) <= 0x11FF

# Apply Latin replacements first
for src, dst in LATIN.items():
    txt = txt.replace(src, dst)

# Then handle Hangul: replace any journal = { ... Hangul ... } with placeholder
def repl_journal(m):
    val = m.group(1)
    if any(is_hangul(c) for c in val):
        return 'journal = {Korean Society Journal (in Korean)}'
    return m.group(0)
txt = re.sub(r'journal\s*=\s*\{([^}]*)\}', repl_journal, txt)

# Catch any remaining non-ASCII -> '?'
def scrub(m):
    return '?'
txt2 = re.sub(r'[^\x00-\x7f]', scrub, txt)

remaining = sum(1 for c in txt2 if ord(c) > 127)
print(f'After sanitize, non-ASCII remaining: {remaining}')

BIB.write_text(txt2, encoding='utf-8')
print(f'Wrote sanitized refs.bib ({len(txt2)} chars)')
