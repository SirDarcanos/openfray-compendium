# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 OpenFray contributors
#
# Extract the SRD 5.2.1 bestiary from WotC's official CC-BY PDF into structured
# per-creature blocks (header lines + font-segmented section entries), the
# intermediate consumed by scripts/ingest-srd52.ts.
#
#   pip install pdfplumber
#   python scripts/extract-srd52-pdf.py SRD_CC_v5.2.1.pdf srd52-blocks.json
#
# Why Python: the two-column stat-block layout needs column cropping and the
# entry names are only reliably found by font (Optima-BoldItalic), both of which
# pdfplumber handles cleanly. The PDF is downloaded separately (not committed);
# get it from https://www.dndbeyond.com/srd under CC-BY-4.0.
#
# Approach: crop each page into L/R columns; anchor each creature on its
# "AC N Initiative" line (name two lines above); take the header from plain text
# extraction (correct line clustering) and segment Traits/Actions/… entries by
# the bold-italic font. Blocks without a parsed header/page are dropped — that
# bounds output to the Monsters A–Z bestiary and excludes magic-item stat blocks
# (e.g. the Figurine-of-Wondrous-Power Giant Fly), per docs and project memory.

import json
import re
import sys

import pdfplumber

BI = "BoldItalic"
LABELS = {"Traits", "Actions", "Bonus Actions", "Reactions", "Legendary Actions"}
TIER = re.compile(r"^(At Will|\d+\s*/\s*Day)\b", re.I)
NOISE = re.compile(
    r"^(System Reference Document 5\.2(?:\.\d)? ?\d*|\d+ System Reference Document 5\.2(?:\.\d)?|Monsters A.Z)$"
)

PDF = sys.argv[1] if len(sys.argv) > 1 else "SRD_CC_v5.2.1.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "srd52-blocks.json"
pdf = pdfplumber.open(PDF)
ac_pages = [i for i, p in enumerate(pdf.pages) if re.search(r"AC \d+ Initiative", p.extract_text() or "")]
lo, hi = min(ac_pages), max(ac_pages)


def printed_page(page):
    t = page.extract_text() or ""
    m = re.search(r"(\d+)\s+System Reference Document 5\.2|System Reference Document 5\.2\s+(\d+)", t)
    return int(m.group(1) or m.group(2)) if m else None


def crop_text(page, a, b):
    return (page.crop((page.width * a, 0, page.width * b, page.height)).extract_text() or "").replace("−", "-")


# Pass A: text lines (correct line clustering) → per-creature header + source page.
text_stream = []
for idx in range(lo, hi + 1):
    page = pdf.pages[idx]
    pg = printed_page(page)
    for a, b in [(0, 0.5), (0.5, 1.0)]:
        for line in crop_text(page, a, b).splitlines():
            line = line.rstrip()
            if line.strip() and not NOISE.match(line.strip()):
                text_stream.append({"t": line, "pg": pg})

ac_a = [i for i, s in enumerate(text_stream) if re.match(r"^AC \d+ Initiative", s["t"])]
headers = {}
for k, ai in enumerate(ac_a):
    name = text_stream[ai - 2]["t"].strip()
    end = ac_a[k + 1] - 2 if k + 1 < len(ac_a) else len(text_stream)
    hdr = []
    for s in text_stream[ai - 1 : end]:
        if s["t"] in LABELS:
            break
        if s["t"].strip() == name:
            continue
        hdr.append(s["t"])
    headers[name] = {"header": hdr, "sourcePage": text_stream[ai]["pg"]}


# Pass B: font words → section entries split on the bold-italic entry name.
def col_words(page, a, b):
    crop = page.crop((page.width * a, 0, page.width * b, page.height))
    rows = {}
    for w in crop.extract_words(extra_attrs=["fontname"]):
        rows.setdefault(round(w["top"] / 3), []).append(w)
    out = []
    for k in sorted(rows):
        ws = sorted(rows[k], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ws).strip().replace("−", "-")
        if not text or NOISE.match(text):
            continue
        bi = []
        for w in ws:
            if w["fontname"].endswith(BI):
                bi.append(w["text"])
            else:
                break
        out.append({"t": text, "bi": " ".join(bi), "semib": ws[0]["fontname"].endswith("SemiBold")})
    return out


fstream = []
for idx in range(lo, hi + 1):
    page = pdf.pages[idx]
    fstream += col_words(page, 0, 0.5) + col_words(page, 0.5, 1.0)
ac_b = [i for i, s in enumerate(fstream) if re.match(r"^AC \d+ Initiative", s["t"])]


def join(desc, line):
    if desc.endswith("-") and re.search(r"[a-z]-$", desc) and line[:1].islower():
        return desc[:-1] + line
    return (desc + " " + line).strip() if desc else line


blocks = []
for k, ai in enumerate(ac_b):
    name = fstream[ai - 2]["t"].strip()
    end = ac_b[k + 1] - 2 if k + 1 < len(ac_b) else len(fstream)
    sec = None
    sections = {}
    cur = None
    pre = {}
    for s in fstream[ai - 1 : end]:
        if s["t"] in LABELS:
            sec = s["t"]
            sections.setdefault(sec, [])
            cur = None
            continue
        if sec is None:
            continue
        if s["semib"]:  # a creature name — this creature's running header, or the
            continue    # next creature's name bleeding past the block boundary
        if s["bi"] and not TIER.match(s["bi"]) and not s["t"].startswith("Legendary Action Uses"):
            cur = {"name": re.sub(r"\.$", "", s["bi"]).strip(), "text": s["t"][len(s["bi"]) :].lstrip(". ").strip()}
            sections[sec].append(cur)
        elif cur is not None:
            cur["text"] = join(cur["text"], s["t"])
        else:
            pre[sec] = join(pre.get(sec, ""), s["t"])
    h = headers.get(name)
    if not h or not h["header"] or not h["sourcePage"]:
        continue  # non-bestiary mis-anchor (magic-item stat block) — drop
    blocks.append(
        {"name": name, "sourcePage": h["sourcePage"], "header": h["header"], "sections": sections, "preamble": pre}
    )

json.dump(blocks, open(OUT, "w"), ensure_ascii=False)
print(f"pages idx {lo}..{hi} | {len(blocks)} bestiary creatures → {OUT}")
