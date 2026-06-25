# OpenFray Compendium

Data-generation tooling for [OpenFray](https://openfray.app). It ingests SRD and
third-party monster/spell sources into OpenFray's `Creature`/`Spell` schema,
validates the result, and emits the JSON the app ships in `public/compendium/`.

This repo is **build-time only** — the OpenFray app never runs it; it just consumes
the JSON. Keeping the generators (and their toolchains, including a Python PDF
parser) out of the app keeps the app lean and the data reproducible here.

## Sources

| Command | Source | Notes |
|---|---|---|
| `npm run ingest:srd52` | **SRD 5.2.1 creatures via WotC's official CC-BY PDF** | the authoritative 5.2 creature pipeline |
| `npm run ingest:srd52-spells` | **SRD 5.2.1 spells via WotC's official CC-BY PDF** | the authoritative 5.2 spell pipeline |
| `npm run ingest:srd-2014` | SRD 5.1 via [dnd5eapi.co](https://www.dnd5eapi.co) | structured 2014 spellcasting/slots |

All game content is used under **CC-BY-4.0**; the OGL is never used for SRD content.
See OpenFray's `docs/content-licensing.md` and `CREDITS.md`.

> **Open5e is no longer used.** SRD 5.2.1 creatures, spells, and conditions are all
> parsed from WotC's official PDF; the only remaining external feed is dnd5eapi.co for
> SRD 5.1 (its structured 2014 spellcasting maps cleanly to our slot model).

## SRD 5.2.1 from the official PDF

The official **SRD 5.2.1** PDF is the authoritative CC-BY source — it has none of the
gaps the Open5e 5.2 feed did (missing alignments, wrong sizes, a corrupt Octopus,
mangled casting times). Each source is a Python extractor (the PDF is two-column;
pdfplumber handles it) feeding a TS mapper:

```bash
pip install pdfplumber                      # one-time
# download the CC-BY PDF (not committed): https://www.dndbeyond.com/srd

# Spells first (creatures hover-link cast spell names against them):
python scripts/extract-srd52-spells-pdf.py SRD_CC_v5.2.1.pdf output/srd52-spell-blocks.json
npm run ingest:srd52-spells -- output/srd52-spell-blocks.json output/srd-spells.json

# Then creatures (3rd arg = the spells JSON, for prose spell-links):
python scripts/extract-srd52-pdf.py SRD_CC_v5.2.1.pdf output/srd52-blocks.json
npm run ingest:srd52 -- output/srd52-blocks.json output/srd-creatures.json output/srd-spells.json
```

The creature extractor takes each section's verbatim text from `extract_text()` and
uses a font pass only for the order of entry names, then splits the text on them —
robust against row-bucketing artifacts that reorder bold names mid-prose. The spell
extractor instead uses `extract_text(use_text_flow=True)` (content-stream order is the
true reading order) and segments on the `Level N <School>` / `<School> Cantrip` header
that follows each spell name. Both are bounded to their PDF sections; known WotC typos
(e.g. the Archmage's XP) are corrected via an errata map in `src/compendium/srd52.ts`.

## Validate & diff

Self-consistency invariants (save = mod + PB, XP = CR table, HP = dice average, …)
plus a field-level diff against a reference dataset:

```bash
npm run validate -- output/srd-creatures.json                              # invariants only
npm run validate -- output/srd-creatures.json ../openfray/public/compendium/srd-creatures.json  # + diff
```

It exits non-zero on invariant errors, so it can gate an ingest.

## Publishing to the app

Generated JSON lands in `output/` (gitignored). Copy the vetted files into the app:

```bash
cp output/srd-creatures.json output/srd-spells.json ../openfray/public/compendium/
```

## Layout

- `src/schema/` — a vendored copy of OpenFray's `Creature`/`Spell` types (kept in
  sync with the app; the source of truth lives in the app repo).
- `src/compendium/` — the mappers (`srd52`, `srd52spells`, `dnd5eapi`), the
  `spelllinker` text utility, and the
  `validate` harness.
- `scripts/` — the ingest runners, the PDF extractor, and the validator CLI.

```bash
npm install
npm test           # mapper/harness unit tests
npm run typecheck
```
