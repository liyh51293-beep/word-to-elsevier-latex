---
name: docx-to-elsevier
description: Convert a Word (.docx) manuscript into a fully-compiling Elsevier CAS LaTeX project (cas-sc class, numeric [N] citations, all formatting fixes pre-applied). Triggers when the user asks to convert/typeset/排版 a Word document to Elsevier LaTeX, or says "我要排版/转 latex/用 elsevier 模板". Pipeline is deterministic Python scripts — agent's job is to drive them and resolve content-specific issues.
---

# docx → Elsevier LaTeX

Converts a Word manuscript into an Elsevier preprint that compiles cleanly with `pdflatex + bibtex` on TeXLive 2023+ (verified on 2025). Single-column `cas-sc` class, numeric `[1][2]` citations via `natbib`.

## When to use

User provides a `.docx` (typically with figures embedded and a numbered reference list) and wants it as a LaTeX project ready to submit. Common phrasings: "convert this Word to Elsevier latex", "排版成 elsevier 格式", "用 latex 重新排这篇 word".

## What the pipeline produces

```
<project>/
├── _tmp_docx/         # work area (unzipped .docx + intermediate JSON)
│   ├── word/document.xml
│   ├── body.json       (from parse_body.py)
│   └── tables.json     (from extract_tables.py)
└── paper/             # the deliverable
    ├── main.tex
    ├── frontmatter.tex (from build_frontmatter.py)
    ├── body.tex        (from build_body.py)
    ├── refs.bib        (from build_bib.py → sanitize_bib.py)
    ├── figures/        (copied from word/media)
    ├── cas-sc.cls      (must exist on TeXLive)
    └── main.pdf        (final, after pdflatex)
```

## Step-by-step

Run these from inside the project directory (the dir that will contain `_tmp_docx/` and `paper/`). Each script reads `DOCX_TMP` / `PAPER_OUT` env vars, defaulting to `./_tmp_docx` and `./paper`.

```bash
# 0. unzip the docx
python -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall('_tmp_docx')" /path/to/manuscript.docx

# 0.5. copy figures out of the docx
mkdir -p paper/figures
cp _tmp_docx/word/media/* paper/figures/   # rename to fig1.jpg, fig2.jpg, ... in order

# 1. parse Word body → JSON (paragraph styles, text, equations, drawings)
python scripts/parse_body.py

# 2. extract real table structures (rows/cells with gridSpan)
python scripts/extract_tables.py

# 3. build frontmatter.tex (title, authors, affiliations, abstract, keywords)
python scripts/build_frontmatter.py

# 4. build body.tex (sections, paragraphs, figures, tables, equations, \autoref links)
python scripts/build_body.py

# 5. build refs.bib (numeric keys 1..N) from references list
python scripts/build_bib.py

# 6. sanitize refs.bib (kill non-ASCII that pdflatex chokes on)
python scripts/sanitize_bib.py

# 7. copy the bundled main.tex template
cp scripts/main.tex.template paper/main.tex

# 8. compile
cd paper && pdflatex -interaction=nonstopmode main.tex \
            && bibtex main \
            && pdflatex -interaction=nonstopmode main.tex \
            && pdflatex -interaction=nonstopmode main.tex
```

## Things that WILL bite you (learned the hard way)

### Class-level gotchas

1. **`\begin{figure}[H]` is silently ignored by cas-sc** — the class redefines `figure` to take key=value options, not standard placement specifiers. `[H]` becomes a stray key and placement defaults to `t`, so all your figures drift to the end of the doc. **Always use `[pos=H]` (with the `float` package loaded).** Same for tables: `\begin{table}[pos=H]`.

2. **cas-sc forces `\sffamily` in captions and table cells.** The reference Elsevier preprint look is serif. Override by:
   - Redefining `\__make_fig_caption:nn` and `\__make_tbl_caption:nn` in your preamble (see `main.tex.template`) to use `\normalfont` (i.e., serif).
   - Adding `\rmfamily` inside each `\begin{table}` block (build_body.py does this automatically).

3. **`\shorttitle` shows up as a running page header.** Set both `\shorttitle{}` and `\shortauthors{}` to empty AND override `\__cas_head:` to be empty (the empty parbox still consumes vertical space otherwise). main.tex.template does both.

4. **Use `[numbers,sort&compress]` natbib + `unsrtnat.bst`** for the `[1][2,3]` style. cas-sc bundles `cas-model2-names.bst` (author-year only); `unsrtnat.bst` is standard TeXLive.

### Content gotchas

5. **Tables are flattened by `parse_body.py`'s `body.iter()`** — row/cell boundaries are LOST. Never try to reconstruct tables from `body.json`'s TableHead/TableBody runs. `extract_tables.py` parses `<w:tbl> > <w:tr> > <w:tc>` directly, preserving `w:gridSpan`. `build_body.py` consumes `tables.json` by caption-numbered legend ("Table 1" → tables[0], etc.).

6. **Long slash-joined terms overflow `tabularx` columns.** Example: `Microscopic/mesoscopic/macroscopic` is one 34-char token to LaTeX. `build_body.py` inserts `\allowbreak{}` after every `/` in cell text so they can wrap.

7. **Hangul/Cyrillic in `refs.bib` crashes pdflatex.** `sanitize_bib.py` replaces Korean journal names with `Korean Society Journal (in Korean)` placeholder and maps Latin diacritics (`ö`, `é`, ...) to TeX accent macros (`\"{o}`, `\'{e}`).

8. **Mojibake in `body.json`**: cp1252 en-dash often arrives as `'� �'` (two replacement chars). `common.py:fix()` maps `'��' → '--'` and lone `'�' → '-'`.

9. **Citation ranges `[28–30]` must expand to `\cite{28,29,30}`** for natbib's sort&compress to render them as `[28-30]`. `common.py:expand_range()` handles `,`/`-`/`–` separators.

10. **In-text "Figure N" / "Table N" should be hyperlinks.** `common.py:process_text()` rewrites `Figure 1a–h` → `\autoref{fig:1}a--h` (suffix preserved). main.tex.template sets `\figureautorefname` to `Fig.` so they render as "Fig. 1".

### Pipeline gotchas

11. **PDF reader holds a file lock on Windows.** If pdflatex emits "I can't write on file `main.pdf`", close Adobe Reader / WPS.

12. **Image quality:** Word's embedded images are usually already 1000+ px; if any specific figure looks blurry in the PDF, audit with `PIL.Image.open(p).size` — anything < 1500 px wide at \linewidth = lower than 300 DPI. Fetch the original from the publisher (`media.springernature.com/original/...` strips Springer's resize).

## Subagents you can dispatch

- **bib-builder** — re-runs only `build_bib.py` + `sanitize_bib.py` and reports any references that didn't parse cleanly. Use when references change or citations break after a re-import.
- **table-fixer** — diagnoses a specific broken table in `body.tex` by re-reading `tables.json` and re-emitting just that table. Use when the user points at "table N is wrong".

Both live in this plugin's `agents/` folder.

## Verification checklist (after a clean compile)

- `grep -c "Undefined" paper/main.log` → 0
- `grep -cE "^! " paper/main.log` → 0
- `pdftotext -layout paper/main.pdf - | grep -c "?? "` → 0 (no unmapped Unicode)
- All `Fig. N` / `Table N` in body render as blue clickable links (hyperref color default)
- No running page header; footer shows `Preprint submitted to Elsevier · Page N of M`
- Tables have `\hline` between every row, headers in bold serif

## Reusing this skill on a new manuscript

Just point the env vars at your new project, drop the .docx, copy figures, run the 8 commands above. No code changes needed unless the .docx uses unusual paragraph styles — in which case patch `parse_body.py`'s `STYLE_ALIAS` dict and `build_body.py`'s style branches.
