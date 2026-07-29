// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 OpenFray contributors

import { describe, expect, it } from 'vitest'
import { broodCreatures as creatures } from '../../src/compendium/brood.ts'
import { validateDataset } from '../../src/compendium/validate.ts'

// Same gates as the Waking Garden suite: the typed source is where a bad field is
// caught, so the ingest's invariants run on every `npm test`.

describe('Brood & Bloom dataset', () => {
  it('holds twelve creatures, each unique by id and name', () => {
    expect(creatures).toHaveLength(12)
    expect(new Set(creatures.map((c) => c.id)).size).toBe(12)
    expect(new Set(creatures.map((c) => c.name)).size).toBe(12)
  })

  it('passes every invariant the ingest would gate on', () => {
    const report = validateDataset(creatures)
    expect(report.issues).toEqual([])
  })

  it('is tagged as one 5.5 source throughout — grouping rules depend on it', () => {
    for (const c of creatures) {
      expect(c.source).toBe('openfray-brood-bloom')
      expect(c.edition).toBe('5.5')
      expect(c.id.startsWith('openfray-brood-bloom:')).toBe(true)
    }
  })

  it('gives every creature its lore layer — the description is part of the library', () => {
    for (const c of creatures) {
      expect(c.description?.trim(), c.name).toBeTruthy()
    }
  })
})
