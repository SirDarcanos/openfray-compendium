// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 OpenFray contributors

/**
 * Map the structured SRD 5.2 blocks (from scripts/extract-srd52-pdf.py) into our
 * Creature schema and write the compendium JSON.
 *
 *   node scripts/ingest-srd52.ts <structured.json> [out.json]
 *
 * Sourced from WotC's official SRD 5.2 PDF under CC-BY-4.0 (see docs/content-licensing.md).
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { mapSrd52, type Srd52Block } from '../src/compendium/srd52.ts'

const [inPath, outPath = 'output/srd-creatures.json'] = process.argv.slice(2)
if (!inPath) {
  console.error('usage: node scripts/ingest-srd52.ts <structured.json> [out.json]')
  process.exit(2)
}

const blocks: Srd52Block[] = JSON.parse(readFileSync(inPath, 'utf8'))
const creatures = blocks.map(mapSrd52)
writeFileSync(outPath, JSON.stringify(creatures, null, 0))
console.log(`mapped ${creatures.length} creatures → ${outPath}`)
