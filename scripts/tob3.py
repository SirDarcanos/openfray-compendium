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

# A real size/type line: "Large Elemental, Chaotic Neutral", "Medium Swarm of Tiny
# Beasts, Unaligned". Requiring a creature TYPE after the size rejects body-text lines
# that merely start with a size word ("Small or Medium…", "Gargantuan oliphaunt…").
TYPES = "Aberration|Beast|Celestial|Construct|Dragon|Elemental|Fey|Fiend|Giant|Humanoid|Monstrosity|Ooze|Plant|Undead"
SIZE = re.compile(rf"^(Tiny|Small|Medium|Large|Huge|Gargantuan)\s+(Swarm of\s+\w+\s+\w+|{TYPES})\b[^,]*,", re.I)
SECTIONS = {"ACTIONS", "BONUS ACTIONS", "REACTIONS", "LEGENDARY ACTIONS", "MYTHIC ACTIONS", "LAIR ACTIONS", "VILLAIN ACTIONS"}
FIELD = re.compile(r"^(Armor Class|Hit Points|Speed|Saving Throws|Skills|Damage Vulnerabilities|Damage Resistances|Damage Immunities|Condition Immunities|Senses|Languages|Challenge|Proficiency Bonus)\b")

# Product Identity creatures to exclude wholesale — the entries the ToB 3 table of
# contents tags with a category the OGC declaration reserves as PI: Archangels,
# Animal Lords, Archdevils, Demon Lords (none in ToB 3), Fey Ladies, Fey Lords, and
# Fiend Lords. Matched by the distinctive name token. (Cross-checked against Open5e's
# tob3 set, which independently omits these — bar two Open5e errors we don't follow:
# it kept the Animal Lord "Queen of Mammoths" and dropped the OGC "Star Thrall".)
EXCLUDE = [
    "HALA",        # Archangel Hala'ath
    "IILARI",      # Archangel Iilari'jil
    "IORVENSIAV",  # Arch-Devil
    "QUEEN OF MAMMOTHS",  # Animal Lord
    "CORAL QUEEN",        # Fey Lady
    "COUNTESS OF GARLANDS",  # Fey Lady
    "MOTHER MOTH",        # Fey Lady
    "RAINFOREST KING",    # Fey Lord
    "ABHADDANAYLA",       # Fiend Lord
    "MALAABIT",           # Fiend Lord
]


def is_pi(name):
    u = name.upper().replace("’", "'")
    return any(k in u for k in EXCLUDE)


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
            # The stat block is set in SegoeUI **Semi**bold/Semilight; sidebars (magic
            # items, mutation tables) interleaved in the same column use plain SegoeUI
            # Light/Italic for their body — drop those, but keep SegoeUI-Bold (creature
            # names + sidebar headings, sorted out below).
            seg = "Segoe" in f0 and ("Semi" in f0 or ("Bold" in f0 and "Italic" not in f0))
            keep = seg or ("Biondi" in f0 and 7.5 < s0 < 9 and text.upper() in SECTIONS)
            if not keep:
                continue  # drops Verdigris (PI flavor), sidebar body, decorative headings, page furniture
            bi = ""  # leading bold-italic run = a trait/action name
            for s in spans:
                if (s["flags"] & BOLD) and (s["flags"] & ITALIC):
                    bi += s["text"]
                else:
                    break
            # A plain-Bold SegoeUI line is a heading: the creature name (before the
            # size/type line, outside the body) or a sidebar heading that bleeds in.
            hdr = "Segoe" in f0 and "Bold" in f0 and "Semi" not in f0 and "Italic" not in f0
            rows.append({"t": text, "bi": bi, "hdr": hdr, "x": round(ln["bbox"][0]), "top": round(ln["bbox"][1])})
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


# Segment on the size/type line, but only when the line above it is an ALL-CAPS
# creature name — rejects a body line like "…into a Small or Medium Humanoid, …".
anchors = [k for k, l in enumerate(stream) if k and SIZE.match(l["t"]) and not re.search(r"[a-z]", stream[k - 1]["t"])]
blocks, excluded = [], []
for ai, a in enumerate(anchors):
    name = stream[a - 1]["t"].strip()
    if is_pi(name):  # Product Identity (Archangel / Animal Lord / Arch-Devil / Fey Lord-Lady / Fiend Lord)
        excluded.append(name)
        continue
    end = anchors[ai + 1] - 1 if ai + 1 < len(anchors) else len(stream)
    # Drop sidebar headings (`hdr` = plain-Bold lines) from the body — their Light body is
    # already gone (page_lines); this removes the leftover title while KEEPING stat-block
    # lines that flow past the sidebar. The creature's name is at a-1, outside the body.
    body = [l for l in stream[a:end] if not l["hdr"]]
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
print(f"pages idx {lo}..{hi} | {len(blocks)} OGC creature blocks → {OUT}")
print(f"excluded {len(excluded)} Product Identity entries: {excluded}")
