# -*- coding: utf-8 -*-
r"""Parse references from Word document.xml into a numeric-keyed BibTeX file.

Two common reference formats are handled:

  Format A (quoted-title, typical in engineering):
    N. Authors, "Title," Journal vol no. X (year): pages. https://doi.org/...
    N. Authors, "Title," in Proceedings... (year): pages. https://doi.org/...

  Format B (unquoted-title, typical in biomedical / life-sciences):
    N. Authors (YEAR). Title. Journal, vol(issue), pages. https://doi.org/DOI

If no quoted title is found, the parser falls back to splitting on
". " after the parenthesized year (Format B).

The style-id used for bibliography paragraphs varies across documents
('Literature', 'af5', or none at all).  Set BIB_STYLE_IDS in config.py
or override via env var BIB_STYLE.

Output: paper/refs.bib with @article{N,...} keys in document order.
"""
import os, re, sys, io
import xml.etree.ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DOCX_TMP, PAPER_OUT, BIB_STYLE_IDS
DOC_XML = str(DOCX_TMP / "word" / "document.xml")
OUT_BIB = str(PAPER_OUT / "refs.bib")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def get_text(p):
    return ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))

def collect_refs(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    refs = {}  # n -> raw text
    order = []
    for p in root.iter(f'{{{W}}}p'):
        pPr = p.find(f'{{{W}}}pPr')
        style = None
        if pPr is not None:
            ps = pPr.find(f'{{{W}}}pStyle')
            if ps is not None:
                style = ps.get(f'{{{W}}}val')
        # Use configurable style-ids (set BIB_STYLE env var for unusual documents)
        if style not in BIB_STYLE_IDS:
            continue
        txt = get_text(p)
        m = re.match(r'^\s*\[?(\d+)\]?[\.、]?\s+(.*)$', txt, re.S)
        if not m:
            continue
        n = int(m.group(1))
        body = m.group(2).strip()
        if len(body) < 20:
            continue
        if n in refs:
            continue  # take first occurrence
        refs[n] = body
        order.append(n)
    return order, refs


def latex_escape(s):
    if not s:
        return s
    # Don't double-escape — assume input is plain text
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            out.append(r'\textbackslash{}')
        elif c == '&':
            out.append(r'\&')
        elif c == '%':
            out.append(r'\%')
        elif c == '_':
            out.append(r'\_')
        elif c == '#':
            out.append(r'\#')
        elif c == '$':
            out.append(r'\$')
        elif c == '{':
            out.append(r'\{')
        elif c == '}':
            out.append(r'\}')
        elif c == '~':
            out.append(r'\textasciitilde{}')
        elif c == '^':
            out.append(r'\textasciicircum{}')
        else:
            out.append(c)
        i += 1
    return ''.join(out)


# Normalize curly quotes etc.
def normalize(s):
    repl = {
        '“': '"', '”': '"',
        '‘': "'", '’': "'",
        '–': '-', '—': '-', '−': '-',
        ' ': ' ',
        '，': ',', '：': ':', '（': '(', '）': ')',
        '、': ',', '。': '.',
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r'\s+', ' ', s).strip()
    # Drop "(n.d.)" no-date markers; downstream regexes either require a
    # 4-digit year or fall through to year-less handling.
    s = s.replace('(n.d.)', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


DOI_RE = re.compile(r'(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)([^\s,;\]]+)', re.I)
URL_RE = re.compile(r'https?://\S+', re.I)
TITLE_QUOTED_RE = re.compile(r'"([^"]+),?"')
# Pattern: Journal Vol no. Issue (Year): Pages   — pages may be empty
JOURNAL_FULL_RE = re.compile(
    r'^(?P<journal>.+?)\s+(?P<volume>\d+)\s+no\.\s*(?P<number>\d+)\s*\((?P<year>\d{4})\)\s*:\s*(?P<pages>[^\.]*?)\s*$'
)
JOURNAL_VOL_RE = re.compile(
    r'^(?P<journal>.+?)\s+(?P<volume>\d+)\s*\((?P<year>\d{4})\)\s*:\s*(?P<pages>[^\.]*?)\s*$'
)
JOURNAL_YEAR_RE = re.compile(
    r'^(?P<journal>.+?)\s*\((?P<year>\d{4})\)\s*:\s*(?P<pages>[^\.]*?)\s*$'
)
INPROC_RE = re.compile(
    r'^in\s+(?P<booktitle>.+?)\s*\((?P<year>\d{4})\)\s*:\s*(?P<pages>[^\.]*?)\s*$', re.I
)
INPROC_BARE_YEAR_RE = re.compile(
    r'^in\s*\((?P<year>\d{4})\)\s*:\s*(?P<pages>[^\.]*?)\s*$', re.I
)
YEAR_RE = re.compile(r'(?<!\d)(19|20)\d{2}(?!\d)')


def parse_one(n, raw):
    text = normalize(raw)

    # Extract DOI (and remove from text)
    doi = None
    mdoi = DOI_RE.search(text)
    if mdoi:
        doi = mdoi.group(1).rstrip('.,;:')
        text = (text[:mdoi.start()] + text[mdoi.end():]).strip().rstrip('.').strip()

    # Strip any remaining bare URLs (e.g. cnki, handle.net) -> stash as url
    url = None
    murl = URL_RE.search(text)
    if murl:
        url = murl.group(0).rstrip('.,;:')
        text = (text[:murl.start()] + text[murl.end():]).strip().rstrip('.').strip()

    # --- Extract quoted title (Format A) ---
    title = None
    rest_after_title = None
    authors_part = None
    mtitle = TITLE_QUOTED_RE.search(text)
    if mtitle:
        title = mtitle.group(1).strip().rstrip(',').strip()
        authors_part = text[:mtitle.start()].strip().rstrip(',').strip()
        rest_after_title = text[mtitle.end():].strip().lstrip(',').strip().rstrip('.').strip()
    # --- Fallback: unquoted title (Format B) ---
    # Pattern: Authors (YEAR). Title. Venue details.
    # Split at parenthesized year to separate authors from title+venue.
    if not title:
        my = re.search(r'\((\d{4})[a-z]?\)', text)
        if my:
            authors_part = text[:my.start()].strip().rstrip(',;.').strip()
            rest = text[my.end():].strip().lstrip('.').strip()
            # First ". " separates title from venue
            dot = rest.find('. ')
            if dot != -1:
                title = rest[:dot].strip()
                rest_after_title = rest[dot + 2:].strip().rstrip('.').strip()
            else:
                title = rest.strip().rstrip('.').strip()
                rest_after_title = ''

    fields = {}
    entry_type = 'article'

    if title:
        fields['title'] = title
    if doi:
        fields['doi'] = doi
    if url:
        fields['url'] = url

    # Authors
    if authors_part:
        # Split authors on comma, strip "et al."
        authors_part = re.sub(r',?\s*et\s+al\.?', ' and others', authors_part, flags=re.I)
        # Split by comma
        parts = [a.strip() for a in authors_part.split(',') if a.strip()]
        # If last entry is "and others", keep as separate marker
        # Remove trailing periods
        parts = [p.rstrip('.').strip() for p in parts if p.strip()]
        if parts:
            # Use " and " separator (BibTeX standard)
            fields['author'] = ' and '.join(parts)

    # Parse rest_after_title
    rest = rest_after_title or ''
    # Inproceedings detection
    minp = INPROC_RE.match(rest)
    minp_bare = INPROC_BARE_YEAR_RE.match(rest)
    if minp:
        entry_type = 'inproceedings'
        fields['booktitle'] = minp.group('booktitle').strip().rstrip(',').strip()
        fields['year'] = minp.group('year')
        pages = minp.group('pages').strip()
        if pages:
            fields['pages'] = pages.replace('-', '--')
    elif minp_bare:
        entry_type = 'inproceedings'
        fields['year'] = minp_bare.group('year')
        pages = minp_bare.group('pages').strip()
        if pages:
            fields['pages'] = pages.replace('-', '--')
    else:
        m1 = JOURNAL_FULL_RE.match(rest)
        m2 = JOURNAL_VOL_RE.match(rest) if not m1 else None
        m3 = JOURNAL_YEAR_RE.match(rest) if not (m1 or m2) else None
        if m1:
            fields['journal'] = m1.group('journal').strip().rstrip(',').strip()
            fields['volume'] = m1.group('volume')
            fields['number'] = m1.group('number')
            fields['year'] = m1.group('year')
            pages = m1.group('pages').strip()
            if pages:
                fields['pages'] = pages.replace('-', '--')
        elif m2:
            fields['journal'] = m2.group('journal').strip().rstrip(',').strip()
            fields['volume'] = m2.group('volume')
            fields['year'] = m2.group('year')
            pages = m2.group('pages').strip()
            if pages:
                fields['pages'] = pages.replace('-', '--')
        elif m3:
            fields['journal'] = m3.group('journal').strip().rstrip(',').strip()
            fields['year'] = m3.group('year')
            pages = m3.group('pages').strip()
            if pages:
                fields['pages'] = pages.replace('-', '--')
        else:
            # Try to find a year somewhere
            my = YEAR_RE.search(rest)
            if my:
                fields['year'] = my.group(0)
            # If we still don't have a journal, dump the rest as note (in addition)
            # but suppress trivial residue (just colons/parens/whitespace).
            if rest and re.search(r'[A-Za-z]{3}', rest):
                fields['note_extra'] = rest

    # If we totally failed to get title/year, fall back to note-only
    note_only = False
    if 'title' not in fields and 'year' not in fields:
        note_only = True
        fields = {'note': text}
    elif 'title' not in fields:
        # we still have year but no title — emit as note-only too
        note_only = True
        fields = {'note': text}

    return entry_type, fields, note_only


def emit_entry(n, entry_type, fields):
    lines = [f'@{entry_type}{{{n},']
    # Preferred order
    order = ['author', 'title', 'booktitle', 'journal', 'volume', 'number',
             'pages', 'year', 'doi', 'url', 'note', 'note_extra']
    seen = set()
    for k in order:
        if k in fields and fields[k]:
            v = fields[k]
            key_out = 'note' if k == 'note_extra' else k
            lines.append(f'  {key_out:8s}= {{{latex_escape(v)}}},')
            seen.add(k)
    for k, v in fields.items():
        if k in seen or not v:
            continue
        lines.append(f'  {k:8s}= {{{latex_escape(v)}}},')
    # Strip trailing comma on last field
    if lines[-1].endswith(','):
        lines[-1] = lines[-1][:-1]
    lines.append('}')
    return '\n'.join(lines)


def main():
    order, refs = collect_refs(DOC_XML)
    print(f'Total entries found: {len(order)}')
    if order:
        print(f'Number range: {min(order)} - {max(order)}')

    note_only_ids = []
    parsed_entries = []
    sorted_ids = sorted(order)
    for n in sorted_ids:
        raw = refs[n]
        etype, fields, note_only = parse_one(n, raw)
        parsed_entries.append((n, etype, fields, note_only, raw))
        if note_only:
            note_only_ids.append(n)

    print(f'Fully parsed: {len(parsed_entries) - len(note_only_ids)}')
    print(f'Note-only fallback: {len(note_only_ids)}')
    if note_only_ids:
        print(f'Note-only IDs: {note_only_ids}')

    # Write bib
    os.makedirs(os.path.dirname(OUT_BIB), exist_ok=True)
    with open(OUT_BIB, 'w', encoding='utf-8') as fh:
        fh.write('% Auto-generated from Word document.xml. Numeric keys = citation numbers.\n\n')
        for n, etype, fields, note_only, raw in parsed_entries:
            fh.write(emit_entry(n, etype, fields))
            fh.write('\n\n')

    # Print first 3 parsed entries
    print('\n=== First 3 entries ===')
    for n, etype, fields, note_only, raw in parsed_entries[:3]:
        print(emit_entry(n, etype, fields))
        print()


if __name__ == '__main__':
    main()
