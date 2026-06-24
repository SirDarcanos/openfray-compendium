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
| `npm run ingest:srd` | SRD 5.2 via the [Open5e](https://open5e.com) v2 API | original 5.2 pipeline |
| `npm run ingest:srd-2014` | SRD 5.1 via [dnd5eapi.co](https://www.dnd5eapi.co) | structured 2014 spellcasting/slots |
| `npm run ingest:srd52` | **SRD 5.2.1 via WotC's official CC-BY PDF** | the authoritative 5.2 pipeline (see below) |

All game content is used under **CC-BY-4.0**; the OGL is never used for SRD content.
See OpenFray's `docs/content-licensing.md` and `CREDITS.md`.

## SRD 5.2.1 from the official PDF (recommended for 5.2)

The Open5e 5.2 data has systemic gaps (missing alignment on every creature, wrong
sizes, a corrupt Octopus). The official **SRD 5.2.1** PDF is the authoritative,
CC-BY source. Two steps — a Python extractor (the PDF is two-column and segments
entries by font, which pdfplumber handles well), then the TS mapper:

```bash
pip install pdfplumber                      # one-time
# download the CC-BY PDF (not committed): https://www.dndbeyond.com/srd
python scripts/extract-srd52-pdf.py SRD_CC_v5.2.1.pdf output/srd52-blocks.json
npm run ingest:srd52 -- output/srd52-blocks.json output/srd-creatures.json
```

The extractor is bounded to the Monsters A–Z bestiary (it drops magic-item stat
blocks like the Figurine-of-Wondrous-Power Giant Fly). Known WotC typos (e.g. the
Archmage's XP) are corrected via an explicit errata map in `src/compendium/srd52.ts`.

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
- `src/compendium/` — the mappers (`open5e`, `dnd5eapi`, `srd52`) and the
  `validate` harness.
- `scripts/` — the ingest runners, the PDF extractor, and the validator CLI.

```bash
npm install
npm test           # mapper/harness unit tests
npm run typecheck
```
