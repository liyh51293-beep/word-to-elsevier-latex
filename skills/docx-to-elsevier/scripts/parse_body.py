#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parse word/document.xml -> body.json (structured paragraph list).

Walks <w:p> elements and emits a list of dicts describing each paragraph,
preserving style, plain text, OMML equations, drawings, and Head1 numbering.
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DOCX_TMP
DOC_XML = str(DOCX_TMP / "word" / "document.xml")
OUT_JSON = str(DOCX_TMP / "body.json")

# Namespaces
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "r":  "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
for k, v in NS.items():
    ET.register_namespace(k, v)

W = "{%s}" % NS["w"]
M = "{%s}" % NS["m"]


def qn(ns_prefix, local):
    return "{%s}%s" % (NS[ns_prefix], local)


# Pattern for Head1 numbering like "1.", "1.1", "1.1.1", optional trailing dot.
NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,3})\.?\s+(.*)$")

# Map raw styleIds (as found in word/styles.xml) to canonical names used
# by the LaTeX pipeline. The docx uses some custom Chinese style names:
#   af5         -> Bibliography (used for numbered reference list) -> Literature
#   MainText151 -> "样式 Main Text + 行距: 1.5 倍行距1"             -> MainText
STYLE_ALIAS = {
    "af5": "Literature",
    "MainText151": "MainText",
}


def get_pstyle(p):
    pPr = p.find(qn("w", "pPr"))
    if pPr is None:
        return None
    pStyle = pPr.find(qn("w", "pStyle"))
    if pStyle is None:
        return None
    return pStyle.get(qn("w", "val"))


def collect_text_in_order(p, eq_counter):
    """
    Walk paragraph in document order, returning (text, omml_list).

    - <w:t> -> append text
    - <w:tab> -> '\t'
    - <w:br> -> '\n'
    - <m:oMath> / <m:oMathPara> -> append [EQ#N] placeholder, capture raw XML
    - <w:drawing> -> append [IMG] (caller checks for drawings to set style)
    """
    parts = []
    omml_list = []
    has_drawing = False

    # Use iter() but skip descendants of oMath/oMathPara/drawing once handled.
    skip_until = None

    def descend(node):
        nonlocal has_drawing
        tag = node.tag
        # OMML math
        if tag == qn("m", "oMathPara") or tag == qn("m", "oMath"):
            n = eq_counter[0] + 1
            eq_counter[0] = n
            placeholder = "[EQ#%d]" % n
            parts.append(placeholder)
            # Serialize the OMML element back to XML string
            try:
                raw = ET.tostring(node, encoding="unicode")
            except Exception:
                raw = ""
            omml_list.append({"id": n, "tag": tag, "xml": raw})
            return  # don't descend
        if tag == qn("w", "drawing"):
            has_drawing = True
            parts.append("[IMG]")
            return
        if tag == qn("w", "t"):
            if node.text:
                parts.append(node.text)
            return
        if tag == qn("w", "tab"):
            parts.append("\t")
            return
        if tag == qn("w", "br"):
            parts.append("\n")
            return
        if tag == qn("w", "noBreakHyphen"):
            parts.append("-")
            return
        if tag == qn("w", "softHyphen"):
            return
        if tag == qn("w", "sym"):
            ch = node.get(qn("w", "char"))
            if ch:
                try:
                    parts.append(chr(int(ch, 16)))
                except Exception:
                    pass
            return
        # Skip pPr (paragraph properties) entirely
        if tag == qn("w", "pPr"):
            return
        # Otherwise descend children
        for child in list(node):
            descend(child)

    for child in list(p):
        descend(child)

    text = "".join(parts)
    return text, omml_list, has_drawing


def parse_document():
    tree = ET.parse(DOC_XML)
    root = tree.getroot()
    body = root.find(qn("w", "body"))
    if body is None:
        print("ERROR: <w:body> not found")
        sys.exit(1)

    paragraphs = []
    eq_counter = [0]  # mutable

    for p in body.iter(qn("w", "p")):
        raw_style = get_pstyle(p) or "MainText"
        style = STYLE_ALIAS.get(raw_style, raw_style)
        text, omml_list, has_drawing = collect_text_in_order(p, eq_counter)
        # Per-paragraph trim
        text_stripped = text.strip()

        entry = {"style": style, "text": text_stripped}
        if raw_style != style:
            entry["raw_style"] = raw_style

        if has_drawing:
            # Override style to "Figure" per spec
            entry["style"] = "Figure"
            if not text_stripped:
                entry["text"] = "[IMG]"

        if omml_list:
            entry["omml"] = omml_list

        # Head1 numbering detection
        if entry["style"] == "Head1":
            m = NUM_RE.match(text_stripped)
            if m:
                num = m.group(1)
                level = num.count(".") + 1
                # "1" -> level 1; "1.1" -> level 2; "1.1.1" -> level 3
                entry["number"] = num
                entry["level"] = level
            else:
                entry["level"] = 1

        paragraphs.append(entry)

    return paragraphs


def write_json(paragraphs):
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(paragraphs, f, ensure_ascii=False, indent=2)


def summarize(paragraphs):
    print("=" * 60)
    print("PARSE SUMMARY")
    print("=" * 60)
    print("Total paragraphs: %d" % len(paragraphs))
    print()

    style_counter = Counter(p["style"] for p in paragraphs)
    print("Style histogram:")
    for style, n in style_counter.most_common():
        print("  %-25s %5d" % (style, n))
    print()

    # First 3 paragraphs after each Head1
    print("Head1 sections (with first 3 following paragraphs):")
    print("-" * 60)
    n_paras = len(paragraphs)
    for i, p in enumerate(paragraphs):
        if p["style"] == "Head1":
            num = p.get("number", "")
            lvl = p.get("level", 1)
            print("[Head1 L%d %s] %s" % (lvl, num, p["text"][:120]))
            shown = 0
            j = i + 1
            while j < n_paras and shown < 3:
                q = paragraphs[j]
                if q["style"] == "Head1":
                    break
                txt = q["text"][:100].replace("\n", " ")
                print("    (%s) %s" % (q["style"], txt))
                shown += 1
                j += 1
            print()

    lit_count = style_counter.get("Literature", 0)
    print("Total Literature paragraphs: %d" % lit_count)
    print()
    print("Output written: %s" % OUT_JSON)


def main():
    paragraphs = parse_document()
    write_json(paragraphs)
    summarize(paragraphs)


if __name__ == "__main__":
    main()
