"""Path config used by every script in this plugin.

By default the scripts assume a project layout like:

    <project>/
        _tmp_docx/      # unzipped .docx + intermediate JSON
            word/document.xml
            body.json (generated)
            tables.json (generated)
        paper/          # LaTeX output
            main.tex
            body.tex (generated)
            frontmatter.tex (generated)
            refs.bib (generated)
            figures/

Override the location by setting env vars DOCX_TMP and PAPER_OUT
before running the scripts.
"""
import os, pathlib

def _resolve(env_key, default):
    p = os.environ.get(env_key)
    return pathlib.Path(p) if p else pathlib.Path.cwd() / default

DOCX_TMP = _resolve('DOCX_TMP', '_tmp_docx')
PAPER_OUT = _resolve('PAPER_OUT', 'paper')
