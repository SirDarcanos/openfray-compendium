// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 OpenFray contributors

// Map Tome of Beasts 3 blocks (from scripts/tob3.py) into the Creature schema.
// ToB 3 uses the 2014 stat-block format — "Melee Weapon Attack: +9 to hit, reach 5
// ft., one target. Hit: 14 (2d8 + 5) bludgeoning damage", a STR/DEX table, "Challenge
// X (Y XP)" — so the prose parsers here differ from srd52.ts (2024). Open Game Content
// only; the PI flavor and the Lord/Archangel entries are already dropped upstream.

import type { Ability, AbilityScores, DamageType, SaveBonuses, Senses, Size, SkillBonuses, Speeds } from '../schema/primitives.ts'
import type { Action, ActionKind, DamageRoll, Range, Recharge, SaveOutcome, SaveRequirement } from '../schema/action.ts'
import type { Creature, LegendaryActions, Trait } from '../schema/creature.ts'
import { slug } from './srd52.ts'

export interface Tob3Block {
  name: string
  sourcePage: number | null
  header: string[]
  traits: { name: string; text: string }[]
  sections: Record<string, { name: string; text: string }[]>
}

const num = (s: string): number => Number(s.replace(/,/g, ''))
/** Tidy stat-block prose: drop tab artifacts and turn the PDF's "•" into list items. */
const prose = (s: string): string => s.replace(/\t/g, ' ').replace(/\s*•\s*/g, '\n- ').replace(/ {2,}/g, ' ').trim()
const normDice = (s: string): string => s.replace(/\s+/g, "").replace(/[–—]/g, "-")
const ABBR: Record<string, Ability> = { str: "str", dex: "dex", con: "con", int: "int", wis: "wis", cha: "cha" }

const DAMAGE = /\d+\s*\(([0-9dD]+(?:\s*[+-]\s*\d+)?)\)\s*([A-Za-z]+)\s+damage/g
function parseDamage(text: string): DamageRoll[] | undefined {
  const out: DamageRoll[] = []
  for (const m of text.matchAll(DAMAGE)) out.push({ formula: normDice(m[1]), type: m[2].toLowerCase() as DamageType })
  return out.length ? out : undefined
}

const ATTACK = /(Melee or Ranged|Melee|Ranged)\s+(?:Weapon|Spell)\s+Attack:\s*\+(\d+)\s*to hit/i
function parseAttack(text: string): { kind: ActionKind; toHit: number; reach?: number; range?: Range } | null {
  const m = ATTACK.exec(text)
  if (!m) return null
  const reach = /reach\s+(\d+)\s*ft/i.exec(text)
  const rng = /range\s+(\d+)\/(\d+)\s*ft/i.exec(text) ?? /range\s+(\d+)\s*ft/i.exec(text)
  let range: Range | undefined
  if (rng) range = rng[2] ? { normal: Number(rng[1]), long: Number(rng[2]) } : { normal: Number(rng[1]) }
  return { kind: range && !reach ? "ranged" : "melee", toHit: Number(m[2]), reach: reach ? Number(reach[1]) : undefined, range }
}

const SAVE = /DC\s+(\d+)\s+(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+saving throw/i
function parseSave(text: string): SaveRequirement | null {
  const m = SAVE.exec(text)
  if (!m) return null
  const onSave: SaveOutcome = /half as much|half the|halved/i.test(text) ? "half" : parseDamage(text) ? "none" : "negates"
  return { ability: ABBR[m[2].slice(0, 3).toLowerCase()], dc: Number(m[1]), onSave }
}

const RECHARGE_DICE = /\(Recharge\s+(\d)(?:\s*[–-]\s*\d)?\)/i
const RECHARGE_DAY = /\((\d+)\s*\/\s*Day\)/i
function parseRecharge(name: string): { recharge?: Recharge; clean: string } {
  const d = RECHARGE_DICE.exec(name)
  if (d) return { recharge: { type: "dice", value: Number(d[1]) }, clean: name.replace(d[0], "").trim() }
  const p = RECHARGE_DAY.exec(name)
  if (p) return { recharge: { type: "perDay", value: Number(p[1]) }, clean: name.replace(p[0], "").trim() }
  return { clean: name.trim() }
}

const COST = /\(Costs?\s+(\d+)\s+Actions?\)/i
function toAction(entry: { name: string; text: string }): Action {
  const costM = COST.exec(entry.name)
  const { recharge, clean } = parseRecharge(entry.name.replace(COST, "").trim())
  const text = `${entry.name}. ${entry.text}`
  const action: Action = { id: slug(clean), name: clean, kind: "utility", toHit: null, text: prose(entry.text) }
  if (recharge) action.recharge = recharge
  if (costM) action.legendaryCost = Number(costM[1])
  const atk = parseAttack(text)
  if (atk) {
    action.kind = atk.kind
    action.toHit = atk.toHit
    if (atk.reach != null) action.reach = atk.reach
    if (atk.range) action.range = atk.range
  } else {
    const save = parseSave(text)
    if (save) { action.kind = "save"; action.save = save }
  }
  const dmg = parseDamage(text)
  if (dmg) action.damage = dmg
  return action
}

const SKILL_KEY: Record<string, keyof SkillBonuses> = {
  acrobatics: "acrobatics", "animal handling": "animalHandling", arcana: "arcana", athletics: "athletics",
  deception: "deception", history: "history", insight: "insight", intimidation: "intimidation",
  investigation: "investigation", medicine: "medicine", nature: "nature", perception: "perception",
  performance: "performance", persuasion: "persuasion", religion: "religion", "sleight of hand": "sleightOfHand",
  stealth: "stealth", survival: "survival",
}

function parseSpeed(s: string): Speeds {
  const sp: Speeds = {}
  const walk = /^(\d+)\s*ft/.exec(s)
  if (walk) sp.walk = Number(walk[1])
  for (const k of ["fly", "swim", "climb", "burrow"] as const) {
    const m = new RegExp(`${k}\\s+(\\d+)\\s*ft`, "i").exec(s)
    if (m) sp[k] = Number(m[1])
  }
  if (/fly[^.,]*\(hover\)/i.test(s)) sp.hover = true
  return sp
}

function parseSenses(s: string): Senses {
  const pp = /passive Perception\s+(\d+)/i.exec(s)
  const out: Senses = { passivePerception: pp ? Number(pp[1]) : 10 }
  for (const k of ["darkvision", "blindsight", "tremorsense", "truesight"] as const) {
    const m = new RegExp(`${k}\\s+(\\d+)`, "i").exec(s)
    if (m) out[k] = Number(m[1])
  }
  return out
}

const list = (s: string): string[] =>
  s.split(/[,;]| and /).map((x) => x.trim()).filter((x) => x && x !== "—" && !/^None$/i.test(x))

/** Header lines → a label→value map (continuations joined) plus the ability table. */
function parseHeader(rawHeader: string[]) {
  // The PDF mixes dash glyphs (hyphen, en/em dash, U+2212 minus) in negative
  // modifiers like "9(−1)"; normalize them so the ability/save/skill parsers match.
  const header = rawHeader.map((l) => l.replace(/[−–—]/g, "-"))
  const FIELD = /^(Armor Class|Hit Points|Speed|Saving Throws|Skills|Damage Vulnerabilities|Damage Resistances|Damage Immunities|Condition Immunities|Senses|Languages|Challenge|Proficiency Bonus)\b\s*(.*)$/
  const fields: Record<string, string> = {}
  const abilNames: string[] = [], abilVals: number[] = []
  let cur: string | null = null
  // The ability row may pack several labels/values per line ("STR  DEX", "28 (+9) 10 (+0)").
  const ABIL = /^(STR|DEX|CON|INT|WIS|CHA)(\s+(STR|DEX|CON|INT|WIS|CHA))*$/i
  const VALS = /^(\d+\s*\([+-]?\d+\)\s*)+$/
  for (const raw of header.slice(1)) {
    const line = raw.replace(/\s+/g, " ").trim()
    const f = FIELD.exec(raw)
    if (f) { cur = f[1]; fields[cur] = f[2]; continue }
    if (ABIL.test(line)) { for (const t of line.split(" ")) abilNames.push(t.toLowerCase()); cur = null; continue }
    if (VALS.test(line)) { for (const m of line.matchAll(/(\d+)\s*\([+-]?\d+\)/g)) abilVals.push(Number(m[1])); cur = null; continue }
    if (cur) fields[cur] = `${fields[cur]} ${raw}`.trim()
  }
  const abilities = {} as AbilityScores
  abilNames.forEach((n, i) => { if (n in ABBR && abilVals[i] != null) abilities[ABBR[n]] = abilVals[i] })
  // Keep the schema valid (and the app safe) when a two-column quirk hides a value.
  for (const k of ["str", "dex", "con", "int", "wis", "cha"] as Ability[]) if (abilities[k] == null) abilities[k] = 10
  return { sizeType: header[0] ?? "", fields, abilities }
}

function bonuses(s: string): Partial<Record<string, number>> {
  const out: Record<string, number> = {}
  for (const m of s.matchAll(/(Str|Dex|Con|Int|Wis|Cha)\s*([+\-–]\d+)/gi)) out[ABBR[m[1].slice(0, 3).toLowerCase()]] = Number(m[2].replace("–", "-"))
  return out
}

function skills(s: string): SkillBonuses {
  const out: SkillBonuses = {}
  for (const m of s.matchAll(/([A-Za-z][A-Za-z ]*?)\s*([+\-–]\d+)/g)) {
    const key = SKILL_KEY[m[1].trim().toLowerCase()]
    if (key) out[key] = Number(m[2].replace("–", "-"))
  }
  return out
}

export function mapTob3(block: Tob3Block): Creature {
  const { sizeType, fields, abilities } = parseHeader(block.header)
  const stM = /^(Tiny|Small|Medium|Large|Huge|Gargantuan)(?:\s+or\s+Small)?\s+(.+?),\s*(.+)$/i.exec(sizeType)
  const size = (stM ? stM[1] : "Medium") as Size
  const type = stM ? stM[2].toLowerCase().replace(/\s*\(.*\)\s*/, " ").trim() : "creature"
  const alignment = stM ? stM[3].trim().toLowerCase() : undefined

  const hpM = /(\d+)\s*\(([^)]+)\)/.exec(fields["Hit Points"] ?? "")
  const crM = /^([\d/]+)\s*\(([\d,]+)\s*XP\)/.exec(fields["Challenge"] ?? "")
  const cr = crM ? (crM[1].includes("/") ? Number(crM[1].split("/")[0]) / Number(crM[1].split("/")[1]) : Number(crM[1])) : undefined
  const dexMod = abilities.dex != null ? Math.floor((abilities.dex - 10) / 2) : 0

  const creature: Creature = {
    id: `kobold-press-tob3:${slug(block.name)}`,
    source: "kobold-press-tob3",
    edition: "5.0",
    name: titleCase(block.name),
    size,
    type,
    ac: Number((fields["Armor Class"] ?? "0").match(/\d+/)?.[0] ?? 0),
    maxHp: hpM ? Number(hpM[1]) : 0,
    initiative: dexMod,
    speed: parseSpeed(fields["Speed"] ?? ""),
    abilities,
    senses: parseSenses(fields["Senses"] ?? ""),
  }
  if (block.sourcePage != null) creature.sourcePage = block.sourcePage
  if (alignment) creature.alignment = alignment
  if (hpM) creature.hpFormula = normDice(hpM[2])
  if (cr != null) creature.cr = cr
  if (crM) creature.xp = num(crM[2])
  const sv = bonuses(fields["Saving Throws"] ?? "") as SaveBonuses
  if (Object.keys(sv).length) creature.saves = sv
  const sk = skills(fields["Skills"] ?? "")
  if (Object.keys(sk).length) creature.skills = sk
  if (fields["Damage Resistances"]) creature.resistances = list(fields["Damage Resistances"])
  if (fields["Damage Immunities"]) creature.immunities = list(fields["Damage Immunities"])
  if (fields["Damage Vulnerabilities"]) creature.vulnerabilities = list(fields["Damage Vulnerabilities"])
  if (fields["Condition Immunities"]) creature.conditionImmunities = list(fields["Condition Immunities"])
  if (fields["Languages"]) { const l = list(fields["Languages"]); if (l.length) creature.languages = l }

  const traits: Trait[] = []
  for (const t of block.traits) {
    const lr = /Legendary Resistance\s*\((\d+)\/Day\)/i.exec(t.name)
    if (lr) creature.legendaryResistance = Number(lr[1])
    traits.push({ name: t.name, text: prose(t.text) })
  }
  if (traits.length) creature.traits = traits

  const actions = (block.sections["Actions"] ?? []).map(toAction)
  if (actions.length) creature.actions = actions
  const bonus = (block.sections["Bonus Actions"] ?? []).map(toAction)
  if (bonus.length) creature.bonusActions = bonus
  const reactions = (block.sections["Reactions"] ?? []).map(toAction)
  if (reactions.length) creature.reactions = reactions
  const legendary = (block.sections["Legendary Actions"] ?? []).map(toAction)
  if (legendary.length) {
    const la: LegendaryActions = { perRound: 3, actions: legendary }
    creature.legendaryActions = la
  }
  return creature
}

function titleCase(s: string): string {
  return s.toLowerCase().replace(/\b([a-z])/g, (c) => c.toUpperCase()).replace(/'([A-Z])/g, (m, c) => "'" + c.toLowerCase())
}
