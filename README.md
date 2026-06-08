# word-to-elsevier-latex

A Claude Code plugin that converts a Word (.docx) manuscript into a clean Elsevier CAS LaTeX project (`cas-sc` class, numeric `[1][2]` citations) that compiles to PDF with `pdflatex + bibtex` on TeXLive 2023+.

Encodes **19 specific gotchas** learned from real-world conversions (styled and unstyled docx, WMF equation images, long tables, etc.) so you don't repeat them.

## Install

Drop under `~/.claude-local-plugins/` (or wherever your Claude Code edition discovers plugins):

```
~/.claude-local-plugins/word-to-elsevier-latex/
```

Restart Claude Code. The skill triggers automatically when you say "排版成 elsevier" / "convert to Elsevier LaTeX" / `/word2tex`.

## Usage

| Style | Input |
|---|---|
| Short slash | `/word2tex <path-to-docx>` |
| Full skill | `docx-to-elsevier` |
| Natural language | "把这个 word 转 elsevier latex" / "把这个 word 排成 latex 格式" |

## What the pipeline handles automatically

| Capability | Detail |
|---|---|
| **Paragraphs** | Styles → `\section{…}`, `\subsection{…}`, body text |
| **Frontmatter** | Title, authors, affiliations, corresponding author, abstract, keywords |
| **Inline equations** | OMML Office Math → LaTeX (`$X_t$`, `$\sigma(\cdot)$`, `$h_t^{bi}$`, etc.) via `omml2tex.py` |
| **Display equations** | Auto-converted from OMML; WMF-embedded equations require manual transcription (see gotcha #14) |
| **Figures** | Embedded images extracted; smart sizing by aspect ratio (portrait figures height-capped, landscape full-width) |
| **Tables** | Three-line style (booktabs `\toprule`/`\midrule`/`\bottomrule`); 8+ row tables use `longtable` so they split across pages with repeated headers |
| **Citations** | `[1]` `[2,3]` `[28–30]` → `\cite{1}` `\cite{2,3}` `\cite{28,29,30}` with `natbib` sort&compress |
| **Cross-references** | `Figure 1` / `Table 2` → `\autoref{fig:1}` / `\autoref{tab:2}` (blue clickable links) |
| **References** | Numbered list → `refs.bib` (two formats: quoted-title and unquoted-title); non-ASCII sanitized |
| **Unicode** | 80+ Unicode→LaTeX mappings: Greek, math symbols, Latin diacritics, Chinese punctuation, Turkish letters |

## Project layout produced

```
<project>/
├── _tmp_docx/           # intermediate work area (delete when done)
│   ├── word/document.xml
│   ├── body.json          (from parse_body.py)
│   ├── tables.json        (from extract_tables.py)
│   ├── eqtex.json         (from omml2tex.py)
│   ├── frontmatter.tex    (from build_frontmatter.py)
│   └── body.tex           (from build_body.py)
└── paper/               # the deliverable
    ├── main.tex           ← single file (from build_main.py)
    ├── refs.bib           (from build_bib.py → sanitize_bib.py)
    ├── figures/
    └── main.pdf           (compiled with elsarticle-num.bst)
```

Only **one `.tex` file** in the final output.

## Pipeline (10 steps)

```bash
# 0. unzip
python -c "import zipfile; zipfile.ZipFile('ms.docx').extractall('_tmp_docx')"

# 0.5. copy figures
mkdir -p paper/figures && cp figures/* paper/figures/

# 1. parse body
python scripts/parse_body.py

# 1.5. convert OMML equations
python scripts/omml2tex.py

# 2. extract tables
python scripts/extract_tables.py

# 3-4. build frontmatter + body
python scripts/build_frontmatter.py
python scripts/build_body.py

# 5-6. build + sanitize references
python scripts/build_bib.py
python scripts/sanitize_bib.py

# 7. assemble single main.tex
python scripts/build_main.py

# 8. compile
cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Important — what your .docx must contain

The pipeline reads only what's already in the `.docx`:

1. **Complete frontmatter** — title, all authors + affiliations, abstract, keywords.
2. **Numbered reference list** (`[1]`, `[2]`, … with full entries including DOI). References stored only in EndNote/Zotero aren't visible.
3. **Figures as embedded images** (or provide high-res `figN.jpg` in a separate folder). Low-quality previews produce blurry PDF.
4. **Numeric in-text citations** `[N]` (not author-year). Ranges like `[1-3]` are expanded automatically.

## Sub-agents

| Agent | Use when |
|---|---|
| **bib-builder** | References break or bibtex emits warnings |
| **table-fixer** | A specific table renders wrong (overflow, misalignment) |
| **omml2tex** | OMML equations need re-converting after docx changes |

## Gotchas already handled (19 total — full list in SKILL.md)

### Class-level
- `cas-sc` silently drops `[H]` → uses `[pos=H]`
- `cas-sc` forces `\sffamily` → serif captions and table cells
- Running page header → `\__cas_head:` overridden to empty
- `elsarticle-num.bst` (official Elsevier numeric, prints DOIs)

### Content
- Long slash-joined terms overflow `tabularx` → `\allowbreak{}` after `/`
- Non-Latin in `refs.bib` crashes pdflatex → sanitized
- Citation ranges `[28–30]` expanded to `{28,29,30}`
- Figure/Table refs → `\autoref` hyperlinks
- Tall figures leave empty pages → ratio-based smart sizing
- Large tables eject to next page → `longtable` for 8+ rows
- Unquoted-title references (biomedical format) → fallback parser
- Chinese/Turkish Unicode → mapped to LaTeX accents
- WPS cloud-sync PDF file lock on Windows

### Pipeline
- Unstyled .docx (all `MainText`) → custom builder pattern documented
- WMF-embedded display equations → Windows GDI+ render + manual transcription

## License

MIT. Use at your own risk on your own manuscripts.
