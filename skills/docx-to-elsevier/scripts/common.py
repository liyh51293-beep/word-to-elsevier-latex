"""Helpers shared by frontmatter and body scripts."""
import re

def fix(text):
    if not text: return text
    text = text.replace('��', '--')
    text = text.replace('�', '-')
    return text

LATEX_SPECIALS = {'&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_',
                  '{':r'\{','}':r'\}',
                  '~':r'\textasciitilde{}','^':r'\textasciicircum{}'}

UNICODE_MAP = {
    '°':r'$^{\circ}$', '×':r'$\times$', '±':r'$\pm$',
    '≤':r'$\leq$', '≥':r'$\geq$', '≈':r'$\approx$', '≠':r'$\neq$',
    '∼':r'$\sim$', '−':r'$-$',
    'α':r'$\alpha$', 'β':r'$\beta$', 'γ':r'$\gamma$', 'δ':r'$\delta$',
    'λ':r'$\lambda$', 'μ':r'$\mu$', 'π':r'$\pi$', 'ρ':r'$\rho$',
    'σ':r'$\sigma$', 'τ':r'$\tau$', 'φ':r'$\varphi$', 'ω':r'$\omega$',
    'Δ':r'$\Delta$', 'Φ':r'$\Phi$', 'Ω':r'$\Omega$', 'θ':r'$\theta$',
    'η':r'$\eta$', 'ε':r'$\varepsilon$',
    'µ':r'$\mu$',  # micro sign (U+00B5), not Greek mu
    '–':'--', '—':'---', '‐':'-', '­':'',
    ' ':'~', ' ':r'\,', '​':'',
    '→':r'$\to$', '′':"'", '·':r'$\cdot$', 'ℓ':r'$\ell$',
    '“':'``', '”':"''", '‘':'`', '’':"'",
    '•':r'$\bullet$', '…':r'\ldots{}',
    '、':', ',
    '®':r'\textsuperscript{\textregistered}',
    # Subscript digits
    '₀':r'$_{0}$', '₁':r'$_{1}$', '₂':r'$_{2}$', '₃':r'$_{3}$', '₄':r'$_{4}$',
    '₅':r'$_{5}$', '₆':r'$_{6}$', '₇':r'$_{7}$', '₈':r'$_{8}$', '₉':r'$_{9}$',
    # Superscript digits/signs
    '⁰':r'$^{0}$', '¹':r'$^{1}$', '²':r'$^{2}$', '³':r'$^{3}$', '⁴':r'$^{4}$',
    '⁵':r'$^{5}$', '⁶':r'$^{6}$', '⁷':r'$^{7}$', '⁸':r'$^{8}$', '⁹':r'$^{9}$',
    '⁻':r'$^{-}$', '⁺':r'$^{+}$',
    # Latin diacritics (TeX accent macros — survive any encoding)
    'á':r"\'{a}", 'é':r"\'{e}", 'í':r"\'{i}", 'ó':r"\'{o}", 'ú':r"\'{u}",
    'Á':r"\'{A}", 'É':r"\'{E}", 'Í':r"\'{I}", 'Ó':r"\'{O}", 'Ú':r"\'{U}",
    'à':r'\`{a}', 'è':r'\`{e}', 'ì':r'\`{i}', 'ò':r'\`{o}', 'ù':r'\`{u}',
    'ä':r'\"{a}', 'ë':r'\"{e}', 'ï':r'\"{i}', 'ö':r'\"{o}', 'ü':r'\"{u}',
    'Ä':r'\"{A}', 'Ë':r'\"{E}', 'Ï':r'\"{I}', 'Ö':r'\"{O}', 'Ü':r'\"{U}',
    'â':r'\^{a}', 'ê':r'\^{e}', 'î':r'\^{i}', 'ô':r'\^{o}', 'û':r'\^{u}',
    'ã':r'\~{a}', 'ñ':r'\~{n}', 'õ':r'\~{o}',
    'ç':r'\c{c}', 'Ç':r'\c{C}',
    'š':r'\v{s}', 'č':r'\v{c}', 'ž':r'\v{z}',
    'Š':r'\v{S}', 'Č':r'\v{C}', 'Ž':r'\v{Z}',
    'ė':r'\.{e}', 'ż':r'\.{z}',
    'ą':r'\k{a}', 'ę':r'\k{e}',
    'ł':r'\l{}', 'Ł':r'\L{}',
    'ø':r'\o{}', 'Ø':r'\O{}',
    'ß':r'\ss{}',
    'ū':r'\={u}', 'ī':r'\={i}', 'ā':r'\={a}', 'ē':r'\={e}', 'ō':r'\={o}',
    'ů':r'\r{u}', 'å':r'\r{a}', 'Å':r'\r{A}',
    'ﬁ':'fi', 'ﬂ':'fl',
}

def esc_plain(text):
    out = []
    for ch in text:
        if ch in UNICODE_MAP:
            out.append(UNICODE_MAP[ch])
        elif ch in LATEX_SPECIALS:
            out.append(LATEX_SPECIALS[ch])
        elif ord(ch) > 127:
            out.append('?')
        else:
            out.append(ch)
    return ''.join(out)

def expand_range(s):
    out = []
    s = s.replace('–', '-').replace('—', '-').replace(' ', '')
    for part in s.split(','):
        if re.match(r'^\d+-\d+$', part):
            a, b = part.split('-')
            out += [str(x) for x in range(int(a), int(b) + 1)]
        elif part.isdigit():
            out.append(part)
    return out

def process_text(text):
    text = fix(text)
    store = []
    def sub_cite(m):
        keys = expand_range(m.group(1))
        if not keys: return m.group(0)
        idx = len(store)
        store.append('\\cite{' + ','.join(keys) + '}')
        return f'\x01{idx}\x01'
    text = re.sub(r'\[(\d+(?:[,\-–]\s*\d+)*)\]', sub_cite, text)
    # Convert plain "Figure N" / "Fig. N" / "Table N" to clickable autoref.
    # Suffix letters (Figure 1a, Fig. 2b) are preserved AFTER the autoref.
    def sub_fig(m):
        n = m.group(1); suf = m.group(2) or ''
        idx = len(store)
        store.append(f'\\autoref{{fig:{n}}}{suf}')
        return f'\x01{idx}\x01'
    def sub_tab(m):
        n = m.group(1)
        idx = len(store)
        store.append(f'\\autoref{{tab:{n}}}')
        return f'\x01{idx}\x01'
    text = re.sub(r'\b(?:Figure|Fig\.?)\s*(\d+)([a-z](?:[-–][a-z]|,\s*[a-z])*)?', sub_fig, text)
    text = re.sub(r'\bTable\s*(\d+)\b', sub_tab, text)
    text = esc_plain(text)
    text = re.sub(r'\x01(\d+)\x01', lambda m: store[int(m.group(1))], text)
    return re.sub(r' {2,}', ' ', text).strip()
