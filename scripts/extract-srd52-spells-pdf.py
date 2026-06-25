# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 OpenFray contributors
#
# Extract the SRD 5.2.1 spell descriptions from WotC's official CC-BY PDF into
# structured per-spell blocks, the intermediate consumed by
# scripts/ingest-srd52-spells.ts.
#
#   pip install pdfplumber
#   python scripts/extract-srd52-spells-pdf.py SRD_CC_v5.2.1.pdf srd52-spell-blocks.json
#
# Approach: the spell list is a two-column layout. Crop each page L/R and pull text
# with extract_text(use_text_flow=True) — the content-stream order is the true
# reading order, which avoids the row-bucketing that reorders bold names/headings
# into the prose (the artifact the bestiary extractor fights with a font pass). Each
# spell is a Name line immediately followed by a "Level N <School> (classes)" or
# "<School> Cantrip (classes)" header; the four field lines (Casting Time / Range /
# Components / Duration) follow, then the description. Spells are segmented by those
# header lines. The PDF is downloaded separately (not committed):
# https://www.dndbeyond.com/srd

import json
import re
import sys

import pdfplumber

SCHOOLS = "Abjuration|Conjuration|Divination|Enchantment|Evocation|Illusion|Necromancy|Transmutation"
HEADER = re.compile(rf"^(?:Level [1-9]|(?:{SCHOOLS}) Cantrip)\b.*\(", re.I)
FIELD = re.compile(r"^(Casting Time|Range|Components|Duration):\s*(.*)$")
NOISE = re.compile(r"^(System Reference Document 5\.2(?:\.\d)? ?\d*|\d+ System Reference Document 5\.2(?:\.\d)?|Spell Descriptions|Spell List)$")

PDF = sys.argv[1] if len(sys.argv) > 1 else "SRD_CC_v5.2.1.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "srd52-spell-blocks.json"
pdf = pdfplumber.open(PDF)

spell_pages = [i for i, p in enumerate(pdf.pages) if "Casting Time:" in (p.extract_text() or "")]
lo, hi = min(spell_pages), max(spell_pages)


def printed_page(page):
    t = page.extract_text() or ""
    m = re.search(r"(\d+)\s+System Reference Document 5\.2|System Reference Document 5\.2\s+(\d+)", t)
    return int(m.group(1) or m.group(2)) if m else None


def col_lines(page, a, b):
    crop = page.crop((page.width * a, 0, page.width * b, page.height))
    out = []
    for line in (crop.extract_text(use_text_flow=True) or "").replace("−", "-").splitlines():
        line = line.strip()
        if line and not NOISE.match(line):
            out.append(line)
    return out


# Clean line stream across the spell section, in reading order (L then R per page).
stream = []
for idx in range(lo, hi + 1):
    page = pdf.pages[idx]
    pg = printed_page(page)
    for a, b in [(0, 0.5), (0.5, 1.0)]:
        for line in col_lines(page, a, b):
            stream.append({"t": line, "pg": pg})

# A spell starts at each header line; its name is the line just above it.
header_ix = [i for i, s in enumerate(stream) if HEADER.match(s["t"])]


def join_cont(lines):
    """Join hyphen-split and wrapped lines into one string."""
    out = ""
    for l in lines:
        if out.endswith("-") and re.search(r"[a-z]-$", out) and l[:1].islower():
            out = out[:-1] + l
        else:
            out = (out + " " + l).strip() if out else l
    return out


spells = []
for k, hi_ix in enumerate(header_ix):
    name = stream[hi_ix - 1]["t"].strip()
    src_pg = stream[hi_ix]["pg"]
    end = header_ix[k + 1] - 1 if k + 1 < len(header_ix) else len(stream)  # up to next spell's name line
    body_lines = [s["t"] for s in stream[hi_ix:end]]

    # Header (Level/School/classes) wraps until the line containing the closing ")".
    hdr, i = [], 0
    while i < len(body_lines):
        hdr.append(body_lines[i])
        if ")" in body_lines[i]:
            i += 1
            break
        i += 1
    header_line = join_cont(hdr)

    # Four field lines (Casting Time / Range / Components / Duration). A label's value
    # is on the same line or, for narrow columns, wraps onto following lines. Duration
    # is the last field and single-valued, so once we have its value the body begins.
    fields = {}
    cur = None
    while i < len(body_lines):
        m = FIELD.match(body_lines[i])
        if m:
            cur = m.group(1)
            fields[cur] = m.group(2)
            i += 1
        elif cur == "Duration":
            if not fields["Duration"]:  # value wrapped onto this line
                fields["Duration"] = body_lines[i]
                i += 1
            break  # body follows the Duration value
        elif cur:
            fields[cur] = (fields[cur] + " " + body_lines[i]).strip()
            i += 1
        else:
            break
    text = join_cont(body_lines[i:])

    spells.append({
        "name": name,
        "sourcePage": src_pg,
        "header": header_line,
        "castingTime": fields.get("Casting Time", ""),
        "range": fields.get("Range", ""),
        "components": fields.get("Components", ""),
        "duration": fields.get("Duration", ""),
        "text": text,
    })

json.dump(spells, open(OUT, "w"), ensure_ascii=False)
print(f"pages idx {lo}..{hi} | {len(spells)} spells → {OUT}")
