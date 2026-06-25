// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 OpenFray contributors

import { describe, expect, it } from 'vitest'
import { mapTob3, type Tob3Block } from '../../src/compendium/tob3.ts'

const block = (over: Partial<Tob3Block>): Tob3Block => ({
  name: 'Test',
  sourcePage: 10,
  header: ['Large Aberration, Chaotic Evil'],
  traits: [],
  sections: {},
  ...over,
})

describe('mapTob3 spellcasting', () => {
  const c = mapTob3(
    block({
      name: 'Adult Prismatic Dragon',
      sections: {
        Actions: [
          {
            name: 'Spellcasting',
            text: '. The prismatic dragon casts one of the following spells, requiring no material components and using Intelligence as the spellcasting ability (spell save DC 17): At will: charm person, color spray 1/day: prismatic wall',
          },
        ],
      },
    }),
  )

  it('lifts a Spellcasting action into the structured block', () => {
    expect(c.spellcasting?.ability).toBe('int')
    expect(c.spellcasting?.saveDc).toBe(17)
    expect(c.spellcasting?.groups[0].usage).toEqual({ type: 'atWill' })
    expect(c.spellcasting?.groups[0].spells.map((s) => s.name)).toEqual(['charm person', 'color spray'])
    expect(c.spellcasting?.groups[1].usage).toEqual({ type: 'perDay', per: 1 })
  })

  it('removes Spellcasting from the plain action list', () => {
    expect(c.actions ?? []).not.toContainEqual(expect.objectContaining({ name: 'Spellcasting' }))
  })
})

describe('mapTob3 bulleted "choose one" actions', () => {
  const c = mapTob3(
    block({
      name: 'Ahu-Nixta Mechanon',
      sections: {
        Actions: [
          {
            name: 'Utility Arm',
            text:
              'The mechanon has one of the following attack options: ' +
              '•\t Grabbing Claw. Melee Weapon Attack: +5 to hit, reach 10 ft., one target. Hit: 8 (2d4 + 3) piercing damage. ' +
              '•\t Sonic Disruptor. Ranged Spell Attack: +4 to hit, range 60 ft., one target. Hit: 9 (2d6 + 2) thunder damage. ' +
              '•\t Telekinetic Projector. The mechanon fires a ray. The target must succeed on a DC 13 Strength saving throw or be moved 30 feet.',
          },
        ],
      },
    }),
  )

  it('keeps a framing parent and adds a clickable sub-action per option', () => {
    const names = (c.actions ?? []).map((a) => a.name)
    expect(names).toEqual(['Utility Arm', 'Grabbing Claw', 'Sonic Disruptor', 'Telekinetic Projector'])
  })

  it('parses each option as its real attack/save', () => {
    const by = (n: string) => (c.actions ?? []).find((a) => a.name === n)!
    expect(by('Grabbing Claw').kind).toBe('melee')
    expect(by('Grabbing Claw').toHit).toBe(5)
    expect(by('Sonic Disruptor').kind).toBe('ranged')
    expect(by('Telekinetic Projector').kind).toBe('save')
    expect(by('Telekinetic Projector').save?.dc).toBe(13)
  })
})

describe('mapTob3 prose tidy', () => {
  it('strips the leading "." the extractor leaves on a split entry', () => {
    const c = mapTob3(
      block({
        sections: { Actions: [{ name: 'Frightful Presence', text: '. Each creature must save.' }] },
      }),
    )
    expect(c.actions?.[0].text).toBe('Each creature must save.')
  })
})
