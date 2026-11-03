/**
 * Where a figure came from — one test, used by every screen.
 *
 * This lived inside Analytics as a local helper for about an hour, which is
 * exactly how the position map ended up defined twice in this codebase. A
 * provenance rule that disagrees with itself between two tabs is worse than no
 * rule: the dotted underline is Kumü's claim about its own data, and it has to
 * mean the same thing everywhere it appears.
 *
 * The test matches the one the scouting report generator runs on the backend:
 * only a value the client supplied counts as declared. Everything else was
 * derived from a league anchor, and says so.
 */

export const valueIsDeclared = (p: any): boolean =>
  (p?.market_value_source ?? p?.marketValueSource) === 'client'

/** The class that marks a market value, or '' when the club declared it. */
export const valueMark = (p: any): string =>
  valueIsDeclared(p) ? '' : 'is-estimated'

/** What the mark means, for a title attribute. */
export const valueTitle = (p: any): string =>
  valueIsDeclared(p)
    ? 'Declared by the club'
    : 'Estimated from the league anchor — not declared by the club'

/** Millions, to one decimal, or an em dash. Every money figure in the UI. */
export const money = (v: number | null | undefined, digits = 1): string =>
  typeof v === 'number' ? `€${(v / 1_000_000).toFixed(digits)}M` : '—'
