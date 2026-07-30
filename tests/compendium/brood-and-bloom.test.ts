// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 OpenFray contributors

import { describe, expect, it } from 'vitest'
import { broodAndBloomCreatures as creatures } from '../../src/compendium/brood-and-bloom.ts'
import { validateDataset } from '../../src/compendium/validate.ts'

// Same gates as the Waking Garden suite: the typed source is where a bad field is
// caught, so the ingest's invariants run on every `npm test`.

describe('Brood & Bloom dataset', () => {
  it('holds fifty-eight creatures, each unique by id and name', () => {
    expect(creatures).toHaveLength(58)
    expect(new Set(creatures.map((c) => c.id)).size).toBe(58)
    expect(new Set(creatures.map((c) => c.name)).size).toBe(58)
  })

  it('passes every invariant the ingest would gate on', () => {
    const report = validateDataset(creatures)
    expect(report.issues).toEqual([])
  })

  it('is tagged as one 5.5 source throughout — grouping rules depend on it', () => {
    for (const c of creatures) {
      expect(c.source).toBe('openfray-brood-and-bloom')
      expect(c.edition).toBe('5.5')
      expect(c.id.startsWith('openfray-brood-and-bloom:')).toBe(true)
    }
  })

  it('gives every creature its lore layer — the description is part of the library', () => {
    for (const c of creatures) {
      expect(c.description?.trim(), c.name).toBeTruthy()
    }
  })

  it('keeps the Lazaret chassis identical across the three officers', () => {
    const officers = ['Lazaret Registrar', 'Lazaret Lector', 'Lazaret Prosector'].map((name) =>
      creatures.find((c) => c.name === name),
    )
    const eyes = officers.map((c) => c!.traits!.find((t) => t.name === 'The Trained Eye'))
    for (const eye of eyes) expect(eye).toBeTruthy()
    // Same wording apart from the officer's own noun.
    const normalized = new Set(
      eyes.map((t) => t!.text.replace(/registrar|lector|prosector/, '<officer>')),
    )
    expect(normalized.size).toBe(1)
  })
})
