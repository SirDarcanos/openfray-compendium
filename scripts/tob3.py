# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 OpenFray contributors
#
# Extract the Tome of Beasts 3 bestiary (Kobold Press, OGL 1.0a) into structured
# per-creature blocks, the intermediate consumed by scripts/ingest-tob3.ts.
#
#   pip install pymupdf
#   python scripts/tob3.py "Tome of Beasts 3.pdf" tob3-blocks.json
#
# LICENSE: ToB 3 declares its monster names, descriptions, statistics, and abilities
# as Open Game Content; artwork, sidebars, and "fiction"/story text are Product
# Identity, as are the Animal Lords, Archangels, Archdevils, Demon Lords, Fey Ladies,
# Fey Lords, and Fiend Lords (excluded wholesale — see EXCLUDE). Conveniently the PI
# flavor is set in VerdigrisMVBProText while the stat block is SegoeUI, so we keep
# only the SegoeUI stat block (+ the Biondi section headers) and drop the rest. Within
# the stat block, a trait/action NAME is SegoeUI-SemiboldItalic (bold+italic), a field
# label is SegoeUI-Bold (bold, not italic), and body text is SegoeUI-Semilight. The
# PDF is NOT committed; it's supplied at ingest time.

import json
import re
import sys

import fitz  # pymupdf

SIZE = re.compile(r"^(Tiny|Small|Medium|Large|Huge|Gargantuan)\b.*,", re.I)
SECTIONS = {"ACTIONS", "BONUS ACTIONS", "REACTIONS", "LEGENDARY ACTIONS", "MYTHIC ACTIONS", "LAIR ACTIONS", "VILLAIN ACTIONS"}
FIELD = re.compile(r"^(Armor Class|Hit Points|Speed|Saving Throws|Skills|Damage Vulnerabilities|Damage Resistances|Damage Immunities|Condition Immunities|Senses|Languages|Challenge|Proficiency Bonus)\b")

PDF = sys.argv[1] if len(sys.argv) > 1 else "Tome of Beasts 3.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "tob3-blocks.json"
doc = fitz.open(PDF)

BOLD, ITALIC = 16, 2


def page_lines(page):
    """Stat-block lines only, in column reading order. Per line: text `t`, the
    bold-italic trait/action name `bi` (empty for fields/body), `x`, `top`."""
    mid = page.rect.width / 2
    rows = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            spans = ln["spans"]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            if not text:
                continue
            f0, s0 = spans[0]["font"], spans[0]["size"]
            keep = "Segoe" in f0 or ("Biondi" in f0 and 7.5 < s0 < 9 and text.upper() in SECTIONS)
            if not keep:
                continue  # drops Verdigris (PI flavor), decorative headings, page furniture
            bi = ""  # leading bold-italic run = a trait/action name
            for s in spans:
                if (s["flags"] & BOLD) and (s["flags"] & ITALIC):
                    bi += s["text"]
                else:
                    break
            rows.append({"t": text, "bi": bi, "x": round(ln["bbox"][0]), "top": round(ln["bbox"][1])})
    left = sorted([r for r in rows if r["x"] < mid], key=lambda r: r["top"])
    right = sorted([r for r in rows if r["x"] >= mid], key=lambda r: r["top"])
    return left + right


def printed_no(page):
    return page.number + 1


pages = [i for i in range(doc.page_count) if any(SIZE.match(l["t"]) for l in page_lines(doc[i]))]
lo, hi = min(pages), max(pages)

stream = []
for i in range(lo, hi + 1):
    for l in page_lines(doc[i]):
        l["pg"] = printed_no(doc[i])
        stream.append(l)


def join(a, b):
    if a.endswith("-") and re.search(r"[a-z]-$", a) and b[:1].islower():
        return a[:-1] + b
    return (a + " " + b).strip() if a else b


def entries(rows):
    """Group lines into named trait/action entries; a `bi` line starts a new one."""
    out = []
    for r in rows:
        if r["bi"]:
            name = r["bi"].strip().rstrip(".").strip()
            rest = r["t"][len(r["bi"]):].strip() if r["t"].startswith(r["bi"]) else r["t"]
            out.append({"name": name, "text": rest})
        elif out:
            out[-1]["text"] = join(out[-1]["text"], r["t"])
    return out


# Segment on the size/type line; the name is the kept line just above it.
anchors = [k for k, l in enumerate(stream) if SIZE.match(l["t"])]
blocks = []
for ai, a in enumerate(anchors):
    name = stream[a - 1]["t"].strip()
    end = anchors[ai + 1] - 1 if ai + 1 < len(anchors) else len(stream)
    body = stream[a:end]
    # header runs from the size/type line until the first trait (bold-italic) or section
    h = 0
    while h < len(body) and not body[h]["bi"] and body[h]["t"].upper() not in SECTIONS:
        h += 1
    header = [l["t"] for l in body[:h]]
    rest, sec, sects, trait_rows = body[h:], None, {}, []
    for l in rest:
        u = l["t"].upper()
        if u in SECTIONS:
            sec = "Actions" if u == "ACTIONS" else u.title()
            sects.setdefault(sec, [])
            continue
        (sects[sec] if sec else trait_rows).append(l)
    blocks.append({
        "name": name,
        "sourcePage": stream[a]["pg"],
        "header": header,
        "traits": entries(trait_rows),
        "sections": {k: entries(v) for k, v in sects.items()},
    })

json.dump(blocks, open(OUT, "w"), ensure_ascii=False)
print(f"pages idx {lo}..{hi} | {len(blocks)} creature blocks → {OUT}")
