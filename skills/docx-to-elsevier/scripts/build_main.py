#!/usr/bin/env python3
"""Assemble a single main.tex from the preamble template + frontmatter + body.

Reads:
    main.tex.template  (preamble up to \\begin{document})
    _tmp_docx/frontmatter.tex  (from build_frontmatter.py)
    _tmp_docx/body.tex         (from build_body.py)

Writes:
    paper/main.tex   —  single self-contained file
"""
import pathlib, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DOCX_TMP, PAPER_OUT

TEMPLATE = pathlib.Path(__file__).parent / 'main.tex.template'
FRONTMATTER = DOCX_TMP / 'frontmatter.tex'
BODY = DOCX_TMP / 'body.tex'
OUT = PAPER_OUT / 'main.tex'

preamble = TEMPLATE.read_text(encoding='utf-8')
# Split at \begin{document} — keep everything before it (preamble + \begin{document})
parts = preamble.split(r'\begin{document}', 1)
if len(parts) == 2:
    head = parts[0] + r'\begin{document}'
else:
    head = preamble  # fallback
    print('WARNING: \\begin{document} not found in template')

# Remove the \input{frontmatter.tex} / \input{body.tex} and bib section from
# the template tail — we're inlining everything.
# Everything after \begin{document} up to \end{document} is the old tail;
# we replace it with our own content.

fm = FRONTMATTER.read_text(encoding='utf-8').strip()
bd = BODY.read_text(encoding='utf-8').strip()

BIB_TAIL = r'''
%% ================ REFERENCES ================
\bibliographystyle{elsarticle-num}
\bibliography{refs}

\end{document}
'''

final = '\n'.join([
    head,
    '',
    '%% ================ FRONTMATTER ================',
    fm,
    r'\maketitle',
    '',
    '%% ================ BODY =======================',
    bd,
    BIB_TAIL,
])

OUT.write_text(final, encoding='utf-8')
print(f'Wrote {OUT}  ({OUT.stat().st_size} bytes)')
print(f'  preamble + frontmatter + body + bib config -> single file')
