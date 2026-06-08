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
│   ├── omml.json       (from omml2tex.py --dump-omml)
│   ├── eqtex.json      (from omml2tex.py)
│   ├── body.json       (from parse_body.py)
│   ├── tables.json     (from extract_tables.py)
│   ├── frontmatter.tex (from build_frontmatter.py)
│   └── body.tex        (from build_body.py)
└── paper/             # the deliverable
    ├── main.tex        ← single file (from build_main.py)
    ├── refs.bib        (from build_bib.py → sanitize_bib.py)
    ├── figures/        (copied from word/media)
    └── main.pdf        (final, after pdflatex + bibtex)
```

## Step-by-step

Run these from inside the project directory (the dir that will contain `_tmp_docx/` and `paper/`). Each script reads `DOCX_TMP` / `PAPER_OUT` env vars, defaulting to `./_tmp_docx` and `./paper`.

```bash
# 0. unzip the docx
python -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall('_tmp_docx')" /path/to/manuscript.docx

# 0.5. copy figures out of the docx (or use user-provided high-res versions)
mkdir -p paper/figures
cp _tmp_docx/word/media/* paper/figures/   # rename to fig1.jpg, fig2.jpg, ... in order

# 1. parse Word body → JSON (paragraph styles, text, equations, drawings)
python scripts/parse_body.py

# 1.5. convert inline OMML equations to LaTeX (if the docx has OMML math)
python scripts/omml2tex.py

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

# 7. assemble single main.tex (preamble + frontmatter + body + bib config)
python scripts/build_main.py

# 8. compile (elsarticle-num.bst for Elsevier numeric style)
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

4. **Use `[numbers,sort&compress]` natbib + `elsarticle-num.bst`** for the `[1][2,3]` style with DOIs printed. cas-sc bundles `cas-model2-names.bst` (author-year only); `elsarticle-num.bst` is the official Elsevier numeric style in TeXLive. Falls back to `unsrtnat.bst` if elsarticle-num is unavailable.

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

13. **Unstyled .docx — everything is `MainText`:** Some manuscripts (especially from WPS/Chinese Word) have NO paragraph styles at all. `parse_body.py`'s style-driven logic produces a histogram of 100% `MainText`. You MUST write a custom builder that recovers structure from content patterns: numbered headings (`N. Title`), keywords/abstract prefix lines, figure/table legends, the `References` marker, and unnumbered back-matter sections. See the insulin-pump-LSTM manuscript conversion for the pattern: detect headings with regex, mark table-paragraph ranges via `w:tbl` membership, and use `body.json` offsets to isolate the reference list.

14. **Display equations as embedded WMF images:** Legacy Word documents often store display equations as embedded `.wmf` metafiles (not OMML). `parse_body.py` sees only empty `(1)`, `(2)` paragraphs — the math itself is invisible. On Windows you can render WMF→PNG via `System.Drawing.Image.FromFile()` in PowerShell, then manually transcribe each equation into LaTeX. OMML inline equations (`[EQ#N]` placeholders) ARE captured by `parse_body.py` and can be auto-converted by `omml2tex.py`.

15. **Tables that eject to the next page, leaving the current page half-empty:** The standard `table` environment is a float that won't split. For tables with 8+ rows, `build_body.py` now uses `longtable` (with `\endfirsthead`/`\endhead`/`\endfoot` for repeated headers). `longtable` MUST have `\caption` as the first command (before `\small`/`\rmfamily`) — otherwise `\caption`'s internal `\noalign` breaks. Column specs for `longtable` use `p{}` only (no `>{}` preamble tokens).

16. **Tall/portrait figures leave too much whitespace:** `width=\linewidth` on a tall figure can overflow the page height, but `height=0.65\textheight` leaves the page looking empty. `build_body.py` now supports `FIG_RATIO` (height/width) with tiered sizing: ratio ≥ 1.3 → `height=0.82\textheight`, ratio ≥ 1.0 → `width=0.92\linewidth`, else `width=\linewidth`. Audit with `PIL.Image.open(p).size` to populate `FIG_RATIO`.

17. **References without quoted titles (Format B):** `build_bib.py` originally only handled `"Title,"` (quoted-title) references. Biomedical/life-sciences papers often use `Authors (YEAR). Title. Journal, vol, pages.` without quotes. A fallback now splits on `(YEAR). ` to extract title and venue. If references still parse as note-only, check the log for which IDs failed and adjust the regex.

18. **Missing Unicode in `common.py`:** Chinese full-width punctuation (`，。：；（）`) and Turkish letters (`ı Ş ş İ`) frequently leak into English manuscripts. They've been added to `UNICODE_MAP`. If you see `?` in the output, find the offending character with `Counter(ch for p in data for ch in p['text'] if ord(ch)>127)` and add it to the map.

19. **WPS / cloud-sync PDF file lock:** On Windows, WPS Office or cloud sync may hold a write lock on `main.pdf` after you open it, causing "I can't write on file `main.pdf`" on the next compile. Close the PDF viewer first, or delete `main.pdf` before recompiling.

## Subagents you can dispatch

- **bib-builder** — re-runs only `build_bib.py` + `sanitize_bib.py` and reports any references that didn't parse cleanly. Use when references change or citations break after a re-import.
- **table-fixer** — diagnoses a specific broken table in `body.tex` by re-reading `tables.json` and re-emitting just that table. Use when the user points at "table N is wrong".
- **omml2tex** — converts OMML (Office Math) equations from `_tmp_docx/word/document.xml` into LaTeX and saves to `_tmp_docx/eqtex.json`. `build_body.py` auto-loads this file. Run `python scripts/omml2tex.py` after `parse_body.py`.

All live in this plugin's `agents/` or `scripts/` folders.

## Verification checklist (after a clean compile)

- `grep -c "Undefined" paper/main.log` → 0
- `grep -cE "^! " paper/main.log` → 0
- `pdftotext -layout paper/main.pdf - | grep -c "?? "` → 0 (no unmapped Unicode)
- All `Fig. N` / `Table N` in body render as blue clickable links (hyperref color default)
- No running page header; footer shows `Preprint submitted to Elsevier · Page N of M`
- Tables use three-line style (`\toprule`/`\midrule`/`\bottomrule` from booktabs), headers in bold serif
- Long tables (8+ rows) use `longtable` so they split across pages instead of ejecting

## Reusing this skill on a new manuscript

Just point the env vars at your new project, drop the .docx, copy figures, run the commands above. Key per-paper hooks:

- **No Word styles?** Write a custom builder patterned on the insulin-pump-LSTM conversion: detect headings/content from text patterns, not styles. The core scripts (`parse_body.py`, `extract_tables.py`, `omml2tex.py`) still give you clean structured data.
- **WMF display equations?** Render them via Windows GDI+ → PNG, transcribe into `DISPLAY_EQ` dict in your builder, and emit as `\begin{equation}` blocks.
- **Unusual bibliography style?** Set `BIB_STYLE=af5,MyStyle` env var; `build_bib.py` reads `config.py`'s `BIB_STYLE_IDS`.
- **Figure aspect ratios?** Populate `FIG_RATIO` in `build_body.py` (or pass via JSON) for smart sizing.
- **Stray tables in extraction?** Populate `TABLE_SKIP` in `build_body.py` to exclude spurious 1-cell artefacts.
- **Unusual paragraph style names?** Patch `parse_body.py`'s `STYLE_ALIAS` dict.
