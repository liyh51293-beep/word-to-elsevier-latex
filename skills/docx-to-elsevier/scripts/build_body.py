"""Build body.tex from body.json + tables.json.

Tables are consumed from tables.json (real w:tbl > w:tr > w:tc) in
document order; body.json TableHead/TableBody runs are ignored.

Figures use [pos=H] (float package) to stay anchored in the text flow.
Tall figures use height-capped sizing; wide/landscape use full linewidth.

Tables with 8+ rows are rendered as longtable so they can break across
pages instead of forcing a page eject that leaves the preceding page empty.

Equations: if OMML was converted and saved as eqtex.json (by omml2tex.py),
`[EQ#N]` placeholders are replaced with the corresponding LaTeX.  Otherwise
a hardcoded EQ dict (manuscript-specific) is used as a fallback — edit it
for each paper or delete it and rely on omml2tex.py.
"""
import json, re, pathlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fix, esc_plain, process_text
from config import DOCX_TMP as DOCX, PAPER_OUT as PAPER

data = json.loads((DOCX / 'body.json').read_text(encoding='utf-8'))
tables_data = json.loads((DOCX / 'tables.json').read_text(encoding='utf-8'))

# ---- equation look-up ----------------------------------------------------
# Prefer auto-generated eqtex.json (from omml2tex.py); fall back to a
# manuscript-specific hardcoded dict.  DELETE the EQ dict and run omml2tex.py
# for each new paper — the hardcoded dict is only here as a safety net.
EQ = {}   # <-- fill in per-paper or leave empty; omml2tex.py output wins
_EQ_FILE = DOCX / 'eqtex.json'
if _EQ_FILE.exists():
    _auto = json.loads(_EQ_FILE.read_text(encoding='utf-8'))
    EQ.update({int(k): v for k, v in _auto.items()})
    print(f'Loaded {len(EQ)} equations from eqtex.json')

def replace_equations_in_text(text):
    def sub(m):
        n = int(m.group(1))
        tex = EQ.get(n)
        return f'${tex}$' if tex else m.group(0)
    return re.sub(r'\[EQ\\?#(\d+)\]', sub, text)

# ---- figure sizing -------------------------------------------------------
# Per-figure aspect ratio (height/width).  Add entries here if a specific
# figure needs non-default sizing; omit to use defaults below.
FIG_RATIO = {}   # e.g. {2: 1.20, 6: 1.27} for tall figures

def fig_includegraphics(fnum):
    """Return the \\includegraphics command with smart sizing."""
    r = FIG_RATIO.get(fnum)
    if r is None:
        # Unknown ratio → play it safe with full width
        return f'  \\includegraphics[width=\\linewidth]{{figures/fig{fnum}.jpg}}'
    if r >= 1.3:
        # Very tall / portrait — cap height to fill the page
        return f'  \\includegraphics[height=0.82\\textheight,keepaspectratio]{{figures/fig{fnum}.jpg}}'
    if r >= 1.0:
        # Moderately tall — slightly narrower width avoids page-height overflow
        return f'  \\includegraphics[width=0.92\\linewidth]{{figures/fig{fnum}.jpg}}'
    # Landscape or wide — full width
    return f'  \\includegraphics[width=\\linewidth]{{figures/fig{fnum}.jpg}}'

# ---- helpers -------------------------------------------------------------
def is_fig_legend(t):
    return bool(re.match(r'^(Fig\.?|Figure)\s*\d+', t.strip(), re.I))
def is_table_legend(t):
    return bool(re.match(r'^Table\s*\d+', t.strip(), re.I))
def fig_num(t):
    m = re.match(r'^(?:Fig\.?|Figure)\s*(\d+)', t.strip(), re.I)
    return int(m.group(1)) if m else None
def tab_num(t):
    m = re.match(r'^Table\s*(\d+)', t.strip(), re.I)
    return int(m.group(1)) if m else None

# Map "Table N" (caption-numbered) → index in tables_data.
# Default is 1:1 (N → tables_data[N-1]); override TABLE_SKIP if the docx
# produced a stray single-cell table that must be excluded.
TABLE_SKIP = set()   # e.g. {2} to skip the 3rd extracted table (0-indexed)
def table_for_legend_num(n):
    effective_idx = n - 1
    for s in sorted(TABLE_SKIP):
        if s <= effective_idx:
            effective_idx += 1
    if 0 <= effective_idx < len(tables_data):
        return tables_data[effective_idx]
    return None

# ---- table emission ------------------------------------------------------
def emit_table(t, tnum, cap_tex):
    """Three-line table (booktabs).  Uses longtable for 8+ row tables so
    they can break across pages instead of leaving the preceding page empty."""
    rows = t['rows']
    ncols = t['gridCols'] or max((sum(c['span'] for c in r) for r in rows), default=1)
    use_longtable = len(rows) >= 8

    out = []
    if use_longtable:
        # --- longtable (cross-page) ---
        if ncols >= 5:
            colspec = 'p{0.175\\linewidth}' * ncols
        elif ncols == 4:
            colspec = 'p{0.22\\linewidth}' * ncols
        elif ncols == 3:
            colspec = 'p{0.30\\linewidth}p{0.32\\linewidth}p{0.30\\linewidth}'
        elif ncols == 2:
            colspec = 'p{0.32\\linewidth}p{0.60\\linewidth}'
        else:
            colspec = 'p{0.92\\linewidth}'
        out.append('  \\small')
        out.append('  \\rmfamily')
        out.append('\\begin{longtable}{' + colspec + '}')
        out.append(f'  \\caption{{{cap_tex}}}')
        out.append(f'  \\label{{tab:{tnum}}}\\\\')
        out.append('  \\toprule')
        # header
        cells_hdr = []
        for c in rows[0]:
            txt = replace_equations_in_text(process_text(c['text']))
            txt = re.sub(r'/(?=\S)', r'/\\allowbreak{}', txt)
            if txt:
                txt = f'\\textbf{{{txt}}}'
            sp = c.get('span', 1)
            cells_hdr.append(f'\\multicolumn{{{sp}}}{{c}}{{{txt}}}' if sp > 1 else txt)
        hdr_line = '  ' + ' & '.join(cells_hdr) + ' \\\\'
        out.append(hdr_line)
        out.append('  \\midrule')
        out.append('  \\endfirsthead')
        # repeated header on continuation pages
        out.append('  \\toprule')
        out.append(hdr_line)
        out.append('  \\midrule')
        out.append('  \\endhead')
        out.append('  \\bottomrule')
        out.append('  \\endfoot')
        # data rows
        for row in rows[1:]:
            cells = []
            for c in row:
                txt = replace_equations_in_text(process_text(c['text']))
                txt = re.sub(r'/(?=\S)', r'/\\allowbreak{}', txt)
                sp = c.get('span', 1)
                cells.append(f'\\multicolumn{{{sp}}}{{c}}{{{txt}}}' if sp > 1 else txt)
            out.append('  ' + ' & '.join(cells) + ' \\\\')
        out.append('  \\bottomrule')
        out.append('\\end{longtable}')
    else:
        # --- regular table ---
        out.append('\\begin{table}[pos=H]')
        out.append('  \\centering')
        out.append('  \\small')
        out.append(f'  \\caption{{{cap_tex}}}')
        out.append(f'  \\label{{tab:{tnum}}}')
        out.append('  \\rmfamily')
        if ncols >= 4:
            colspec = '>{\\raggedright\\arraybackslash}X' * ncols
            out.append(f'  \\begin{{tabularx}}{{\\linewidth}}{{{colspec}}}')
            env = 'tabularx'
        elif ncols == 3:
            out.append('  \\begin{tabular}{p{0.30\\linewidth}p{0.32\\linewidth}p{0.30\\linewidth}}')
            env = 'tabular'
        elif ncols == 2:
            out.append('  \\begin{tabular}{p{0.32\\linewidth}p{0.60\\linewidth}}')
            env = 'tabular'
        else:
            out.append('  \\begin{tabular}{p{0.92\\linewidth}}')
            env = 'tabular'
        out.append('  \\toprule')
        for r_idx, row in enumerate(rows):
            cells_tex = []
            for c in row:
                txt = replace_equations_in_text(process_text(c['text']))
                txt = re.sub(r'/(?=\S)', r'/\\allowbreak{}', txt)
                if r_idx == 0 and txt:
                    txt = f'\\textbf{{{txt}}}'
                sp = c.get('span', 1)
                if sp > 1:
                    cells_tex.append(f'\\multicolumn{{{sp}}}{{c}}{{{txt}}}')
                else:
                    cells_tex.append(txt)
            out.append('  ' + ' & '.join(cells_tex) + ' \\\\')
            if r_idx == 0:
                out.append('  \\midrule')
        out.append('  \\bottomrule')
        out.append(f'  \\end{{{env}}}')
        out.append('\\end{table}')
    out.append('')
    return out

# ---------- main walk ----------
out = []; i = 0; n = len(data); fig_used = set()
# Skip frontmatter (until first Head1 with number "1", else start at paragraph 0)
while i < n and not (data[i].get('style') == 'Head1' and data[i].get('number', '') == '1'):
    i += 1
if i >= n:
    i = 0   # fallback: no styled Head1 found → start from beginning

while i < n:
    p = data[i]
    style = p.get('style')
    text = fix(p.get('text', ''))

    if style == 'Head1':
        lvl = p.get('level', 1)
        clean = re.sub(r'^\d+(\.\d+)*\.?\s*', '', text)
        cmd = {1: '\\section', 2: '\\subsection', 3: '\\subsubsection'}.get(lvl, '\\subsection')
        out.append(f'{cmd}{{{esc_plain(clean)}}}')
        out.append('')
        i += 1; continue

    if style == 'MainText':
        if not text.strip():
            i += 1; continue
        low = text.lstrip().lower()
        if low.startswith('keywords:') or low.startswith('funding:'):
            i += 1; continue
        body = replace_equations_in_text(process_text(text))
        out.append(body)
        out.append('')
        i += 1; continue

    if style == 'MTDisplayEquation':
        i += 1; continue

    if style == 'Figure':
        legend = ''; fnum = None
        inline = re.sub(r'^\s*\[IMG\]\s*', '', text)
        if is_fig_legend(inline):
            legend = inline.strip(); fnum = fig_num(legend)
        else:
            for j in range(i + 1, min(i + 5, n)):
                # Also check MainText (some docx don't use 'Legend' style)
                if data[j].get('style') in ('Legend', 'MainText'):
                    lt = fix(data[j]['text']).strip()
                    if is_fig_legend(lt):
                        legend = lt; fnum = fig_num(lt); break
        if fnum is None:
            fnum = next((k for k in range(1, 100) if k not in fig_used), 1)
        fig_used.add(fnum)
        cap = re.sub(r'^(?:Fig\.?|Figure)\s*\d+\.?\s*', '', legend) if legend else ''
        cap_tex = replace_equations_in_text(process_text(cap)) if cap else 'Figure caption.'
        out.append('\\begin{figure}[pos=H]')
        out.append('  \\centering')
        out.append(fig_includegraphics(fnum))
        out.append(f'  \\caption{{{cap_tex}}}')
        out.append(f'  \\label{{fig:{fnum}}}')
        out.append('\\end{figure}')
        out.append('')
        i += 1; continue

    if style == 'Legend':
        if is_fig_legend(text):
            i += 1; continue
        if is_table_legend(text):
            tnum = tab_num(text)
            cap = re.sub(r'^Table\s*\d+\.?\s*', '', text)
            cap_tex = replace_equations_in_text(process_text(cap))
            t = table_for_legend_num(tnum)
            if t is None:
                out.append(f'% [missing table data for Table {tnum}]')
                out.append('')
            else:
                out += emit_table(t, tnum, cap_tex)
            j = i + 1
            while j < n and data[j].get('style') in ('TableHead', 'TableBody'):
                j += 1
            i = j; continue
        i += 1; continue

    if style in ('TableHead', 'TableBody'):
        i += 1; continue

    i += 1

body_tex = '\n'.join(out)
(PAPER / 'body.tex').write_text(body_tex, encoding='utf-8')
(DOCX / 'body.tex').write_text(body_tex, encoding='utf-8')  # for build_main.py
print(f'Wrote body.tex: {len(out)} lines')
print(f'Figures used: {sorted(fig_used)}')
print(f'Tables emitted: {sum(1 for l in out if "begin{table}" in l or "begin{longtable}" in l)}')
