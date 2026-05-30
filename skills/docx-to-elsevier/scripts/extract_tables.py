"""Extract real table structures from word/document.xml.

Walks the body in document order, finding <w:tbl> elements (in order),
and for each emits {rows: [[cell_text, ...], ...], gridCols: int}.

Cell text is the concatenation of all <w:t> within the cell, with paragraph
breaks rendered as ' / ' so multi-paragraph cells stay readable on one row.
"""
import json, os, re, sys
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DOCX_TMP
DOC_XML = str(DOCX_TMP / "word" / "document.xml")
OUT_JSON = str(DOCX_TMP / "tables.json")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def cell_text(tc):
    """Concatenate all w:t in this cell, joining paragraphs with ' / '."""
    paras = []
    for p in tc.iter(W + "p"):
        parts = []
        for t in p.iter(W + "t"):
            if t.text:
                parts.append(t.text)
        s = "".join(parts).strip()
        if s:
            paras.append(s)
    return " / ".join(paras)

def grid_cols(tbl):
    grid = tbl.find(W + "tblGrid")
    if grid is None:
        return 0
    return len(grid.findall(W + "gridCol"))

def extract_rows(tbl):
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            # honor gridSpan: a cell may span multiple columns
            tcPr = tc.find(W + "tcPr")
            span = 1
            if tcPr is not None:
                gs = tcPr.find(W + "gridSpan")
                if gs is not None:
                    span = int(gs.get(W + "val", "1"))
            txt = cell_text(tc)
            cells.append({"text": txt, "span": span})
        rows.append(cells)
    return rows

def main():
    tree = ET.parse(DOC_XML)
    root = tree.getroot()
    body = root.find(W + "body")
    tables = []
    # iterate only over direct children of body (tables live there)
    for el in body.iter(W + "tbl"):
        tables.append({
            "gridCols": grid_cols(el),
            "rows": extract_rows(el),
        })
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(tables, f, ensure_ascii=False, indent=2)
    print(f"Extracted {len(tables)} tables -> {OUT_JSON}")
    for i, t in enumerate(tables, 1):
        nr = len(t["rows"])
        nc = t["gridCols"]
        first = [c["text"][:40] for c in t["rows"][0]] if t["rows"] else []
        print(f"  Table {i}: gridCols={nc}, rows={nr}, first row={first}")

if __name__ == "__main__":
    main()
