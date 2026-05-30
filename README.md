# word-to-elsevier-latex

A Claude Code plugin that converts a Word (.docx) manuscript into a clean Elsevier CAS LaTeX project (`cas-sc` class, numeric `[1][2]` citations) that compiles with `pdflatex + bibtex` on TeXLive 2023+.

Encodes 12 specific gotchas learned from a full real-world conversion so you don't repeat them.

## Install

Drop this folder under `~/.claude/plugins/` (or wherever your Claude Code edition discovers plugins). It will load automatically on next session.

```
~/.claude/plugins/word-to-elsevier-latex/
```

Restart Claude Code, then `/plugin` should show it listed.

## Usage

Three equivalent entry points:

| Style | Input |
|---|---|
| Short slash | `/word2tex <path-to-docx>` |
| Full skill | `/docx-to-elsevier` |
| Natural language | "把这个 word 转 elsevier latex" / "convert this docx to elsevier latex" |

Sub-agents are dispatched automatically:
- **bib-builder** — if references break or bibtex emits warnings
- **table-fixer** — if a specific table renders wrong (overflow, misalignment, missing wrap)

## Important — what your .docx must contain

The pipeline reads only what's already in the `.docx`. Before you run the plugin, **make sure**:

1. **The Word document is complete** — title, all authors and affiliations, abstract, keywords, all body sections, references list, figure captions, table captions.
2. **The references section is in the document** (numbered `[1]`, `[2]`, ... with full bibliography entries — DOI, journal, year, authors). The plugin parses these into `refs.bib` with numeric keys. References stored only in a separate EndNote / Zotero library aren't visible.
3. **Figures are present in the source folder.** The pipeline extracts images embedded in the docx, but if a figure was inserted as a low-quality preview or as a linked image (not embedded), the output PDF will be blurry. **Best practice: put all original high-resolution figures into a `figures/` folder alongside the docx**, named `fig1.jpg`, `fig2.jpg`, ... in citation order. The skill will use these instead of the embedded copies if both are present.
4. **All in-text citations use `[N]` numeric markers** (not author-year), matching the reference list. Ranges like `[1-3]` or `[1–3]` are expanded automatically.

If any of these is missing the output will compile but be incomplete — you'll have to hand-fix the gaps.

## Project layout produced

```
<project>/
├── _tmp_docx/           # intermediate JSON (delete when done)
└── paper/
    ├── main.tex
    ├── frontmatter.tex
    ├── body.tex
    ├── refs.bib
    ├── figures/
    └── main.pdf
```

## Gotchas the plugin already handles

See `skills/docx-to-elsevier/SKILL.md` for the full list. Highlights:
- `cas-sc` silently drops `[H]` placement — uses `[pos=H]`
- `cas-sc` forces `\sffamily` in captions and table cells — overridden to serif
- Long slash-joined terms (`a/b/c/d`) overflow tabularx — `\allowbreak{}` injected after every `/`
- Hangul / non-Latin in `refs.bib` crashes pdflatex — sanitizer replaces them
- `\shorttitle{}` would still leave a running header — `\__cas_head:` is overridden to empty

## License

MIT. Use at your own risk on your own manuscripts.
