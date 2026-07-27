// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 OpenFray contributors

/**
 * Emit the "Brood & Bloom" library — original OpenFray creatures — into the Creature
 * schema JSON the app ships in public/compendium/brood-creatures.json.
 *
 *   node scripts/ingest-brood.ts [out.json]
 *
 * Unlike the SRD / Tome of Beasts pipelines there is no PDF and no prose parser: the
 * creatures are authored directly (and type-checked by tsc) in ../src/compendium/brood.ts.
 * This runner sorts them, runs the shared invariant validator, and refuses to write on any
 * error, so a bad edit can't reach the app. Original content, not OGL/CC-BY — see CREDITS.md.
 */

import { writeFileSync } from 'node:fs'
import { broodCreatures } from '../src/compendium/brood.ts'
import { validateDataset } from '../src/compendium/validate.ts'

const outPath = process.argv[2] ?? 'output/brood-creatures.json'
const creatures = [...broodCreatures].sort((a, b) => a.name.localeCompare(b.name))

const report = validateDataset(creatures)
console.log(`brood: ${report.count} creatures — errors: ${report.errors}, warnings: ${report.warns}`)
if (report.errors) {
  for (const [field, n] of Object.entries(report.errorsByField).sort((a, b) => b[1] - a[1]))
    console.error(`  ${String(n).padStart(4)}  ${field}`)
  process.exit(1)
}

writeFileSync(outPath, JSON.stringify(creatures, null, 0))
console.log(`mapped ${creatures.length} Brood creatures → ${outPath}`)
