"""Build body.tex from body.json + tables.json.

Tables are now consumed from tables.json (real w:tbl > w:tr > w:tc) in
document order; the body.json TableHead/TableBody runs are ignored.

Figures use [H] (float package) to stay anchored in the text flow.
"""
import json, re, pathlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fix, esc_plain, process_text
from config import DOCX_TMP as DOCX, PAPER_OUT as PAPER

data = json.loads((DOCX / 'body.json').read_text(encoding='utf-8'))
tables_data = json.loads((DOCX / 'tables.json').read_text(encoding='utf-8'))

EQ = {
    1: r'F_{\mathrm{th}} \sim \sqrt{\tau_p}',
    2: r'\theta_B = 6.7^{\circ}',
    3: r'E_p = 13\,\mathrm{\mu J}',
    4: r'\theta_B = 6.7^{\circ}',
    5: r'E_p = 13\,\mathrm{\mu J}',
    6: r'\theta_B = 6.7^{\circ}',
    7: r'E_p = 52\,\mathrm{\mu J}',
    8: r'\theta_B = 13.3^{\circ}',
    9: r'E_p = 13\,\mathrm{\mu J}',
}

def replace_equations_in_text(text):
    def sub(m):
        n = int(m.group(1))
        return f'${EQ.get(n, "?")}$'
    return re.sub(r'\[EQ\\?#(\d+)\]', sub, text)

def is_fig_legend(t):
    return bool(re.match(r'^(Fig\.?|Figure)\s*\d+', t.strip(), re.I))
def is_table_legend(t):
    return bool(re.match(r'^Table\s*\d+', t.strip(), re.I))
def fig_num(t):
    m = re.match(r'^(?:Fig\.?|Figure)\s*(\d+)', t.strip(), re.I); return int(m.group(1)) if m else None
def tab_num(t):
    m = re.match(r'^Table\s*(\d+)', t.strip(), re.I); return int(m.group(1)) if m else None

# Drop Table 3 from tables.json (a single-cell stray cell that's actually the
# overflow of Table 2's last row; the real reviewed-papers table is Table 2.)
# Map "Table N" (caption-numbered) -> index in tables_data, skipping stragglers.
USE_TABLE_INDEXES = [0, 1, 3, 4]  # Tables 1,2 then skip the 1-cell stray, then 4,5
def table_for_legend_num(n):
    """Caption-numbered N (1..) -> docx table dict, or None."""
    if 1 <= n <= len(USE_TABLE_INDEXES):
        return tables_data[USE_TABLE_INDEXES[n-1]]
    return None


def emit_table(t, tnum, cap_tex):
    """Render a structured table {gridCols, rows:[[{text,span},...],...]}.

    Use tabularx with X columns so the table fits the linewidth and cells wrap.
    First column is left-aligned 'l' if narrow, else also X.
    """
    rows = t['rows']
    ncols = t['gridCols'] or max((sum(c['span'] for c in r) for r in rows), default=1)
    out = []
    out.append('\\begin{table}[pos=H]')
    out.append('  \\centering')
    out.append('  \\small')
    out.append(f'  \\caption{{{cap_tex}}}')
    out.append(f'  \\label{{tab:{tnum}}}')
    out.append('  \\rmfamily')  # override cas-sc default \sffamily for cell content
    if ncols >= 4:
        colspec = '>{\\raggedright\\arraybackslash}X' * ncols
        out.append(f'  \\begin{{tabularx}}{{\\linewidth}}{{{colspec}}}')
    elif ncols == 3:
        out.append('  \\begin{tabular}{p{0.22\\linewidth}p{0.36\\linewidth}p{0.36\\linewidth}}')
    elif ncols == 2:
        out.append('  \\begin{tabular}{p{0.30\\linewidth}p{0.65\\linewidth}}')
    else:
        out.append('  \\begin{tabular}{p{0.95\\linewidth}}')
    out.append('  \\hline')
    for r_idx, row in enumerate(rows):
        cells_tex = []
        for c in row:
            txt = replace_equations_in_text(process_text(c['text']))
            # Let long slash-joined compound words break inside narrow columns.
            txt = re.sub(r'/(?=\S)', r'/\\allowbreak{}', txt)
            if r_idx == 0 and txt:
                txt = f'\\textbf{{{txt}}}'  # bold header cells
            sp = c.get('span', 1)
            if sp > 1:
                cells_tex.append(f'\\multicolumn{{{sp}}}{{c}}{{{txt}}}')
            else:
                cells_tex.append(txt)
        out.append('  ' + ' & '.join(cells_tex) + ' \\\\')
        out.append('  \\hline')
    if ncols >= 4:
        out.append('  \\end{tabularx}')
    else:
        out.append('  \\end{tabular}')
    out.append('\\end{table}')
    out.append('')
    return out


# ---------- main walk ----------
out = []
i = 0
n = len(data)
fig_used = set()

# Skip frontmatter (until first Head1 with number "1")
while i < n and not (data[i].get('style')=='Head1' and data[i].get('number','')=='1'):
    i += 1

while i < n:
    p = data[i]
    style = p.get('style')
    text = fix(p.get('text',''))

    if style == 'Head1':
        lvl = p.get('level', 1)
        clean = re.sub(r'^\d+(\.\d+)*\.?\s*', '', text)
        cmd = {1:'\\section', 2:'\\subsection', 3:'\\subsubsection'}.get(lvl, '\\subsection')
        out.append(f'{cmd}{{{esc_plain(clean)}}}')
        out.append('')
        i += 1
        continue

    if style == 'MainText':
        if not text.strip(): i += 1; continue
        low = text.lstrip().lower()
        if low.startswith('keywords:') or low.startswith('funding:'):
            i += 1; continue
        body = replace_equations_in_text(process_text(text))
        out.append(body)
        out.append('')
        i += 1
        continue

    if style == 'MTDisplayEquation':
        i += 1
        continue

    if style == 'Figure':
        legend = ''
        fnum = None
        inline = re.sub(r'^\s*\[IMG\]\s*', '', text)
        if is_fig_legend(inline):
            legend = inline.strip(); fnum = fig_num(legend)
        else:
            for j in range(i+1, min(i+5, n)):
                if data[j].get('style') == 'Legend':
                    lt = fix(data[j]['text']).strip()
                    if is_fig_legend(lt):
                        legend = lt; fnum = fig_num(lt); break
        if fnum is None:
            fnum = next((k for k in range(1, 17) if k not in fig_used), None)
        fig_used.add(fnum)
        cap = re.sub(r'^(?:Fig\.?|Figure)\s*\d+\.?\s*', '', legend) if legend else ''
        cap_tex = replace_equations_in_text(process_text(cap)) if cap else 'Figure caption.'
        out.append('\\begin{figure}[pos=H]')
        out.append('  \\centering')
        out.append(f'  \\includegraphics[width=\\linewidth]{{figures/fig{fnum}.jpg}}')
        out.append(f'  \\caption{{{cap_tex}}}')
        out.append(f'  \\label{{fig:{fnum}}}')
        out.append('\\end{figure}')
        out.append('')
        i += 1
        continue

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
            # advance past all consecutive TableHead/TableBody and the stale chunk
            j = i + 1
            while j < n and data[j].get('style') in ('TableHead','TableBody'):
                j += 1
            i = j
            continue
        i += 1
        continue

    if style in ('TableHead','TableBody'):
        i += 1
        continue

    i += 1

(PAPER / 'body.tex').write_text('\n'.join(out), encoding='utf-8')
print(f'Wrote body.tex: {len(out)} lines')
print(f'Figures used: {sorted(fig_used)}')
