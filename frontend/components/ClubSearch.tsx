'use client'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { api } from '@/lib/api'
import { money } from '@/lib/provenance'

/**
 * Club-first search.
 *
 * Every other screen in Kumü starts from a named player. This one starts
 * from the club, which is the direction a scout actually works in: the
 * brief comes from the squad, and the players are what has to be found.
 *
 * Two things here are not cosmetic.
 *
 * COVERAGE. Ranking a population forces a decision that scoring one pair
 * never had to make. A player the brief cannot judge can be dropped - and
 * then missing data erases a person rather than a claim - or filled in,
 * which is the defect this product has spent its life removing. Neither:
 * every row carries what could be assessed about THAT player, and the list
 * can be read by coverage as well as by rank.
 *
 * NEAR MISSES. A filter that silently hides a player one year over the age
 * limit is the opposite of a search. A candidate who fails exactly one
 * stated filter is kept, marked, and placed after the clean matches.
 */

interface Criterion { name: string; assessed: boolean; detail?: string | null }
interface Result {
  rank: number
  player: {
    id: string; name: string; position?: string | null; nationality?: string | null
    current_team?: string | null; age?: number | null
    market_value?: number | null; performance_index?: number | null
  }
  score: { overall: number; tactical: number; performance: number; financial: number; growth: number }
  criteria: Criterion[]
  coverage: number
  near_miss: boolean
  missed?: string | null
}
interface Response {
  team: { id: string; name: string; league: string }
  brief: Criterion[]
  population: number
  considered: number
  results: Result[]
  basis: string
}

const POSITIONS = ['GK', 'RB', 'CB', 'LB', 'CDM', 'CM', 'CAM', 'RM', 'LM', 'RW', 'LW', 'ST']

/**
 * Whether two place names are the same place written differently.
 *
 * In this source a player's club IS his country, so nationality and current
 * team repeat - but they repeat under different conventions: the ISO long
 * form against the common name. An exact-match dedupe catches "Brazil ·
 * Brazil" and sails straight past "United States of America · United
 * States", "Iran, Islamic Republic of · Iran" and "Korea (South) · South
 * Korea". Comparing word sets catches all four, because every one of those
 * pairs has one name's words contained in the other's.
 */
const samePlace = (a: string, b: string) => {
  const words = (s: string) =>
    new Set(
      s.toLowerCase().replace(/[^a-z\s]/g, ' ').split(/\s+/)
        .filter((w) => w && w !== 'of' && w !== 'the' && w !== 'republic'),
    )
  const A = words(a); const B = words(b)
  if (!A.size || !B.size) return false
  const [small, big] = A.size <= B.size ? [A, B] : [B, A]
  return Array.from(small).every((w) => big.has(w))
}

const describe = (position?: string | null, nationality?: string | null,
                  club?: string | null) => {
  const places: string[] = []
  for (const name of [nationality, club]) {
    if (!name) continue
    if (!places.some((p) => samePlace(p, name))) places.push(name)
  }
  return [position, ...places].filter(Boolean).join(' · ')
}

const ClubSearch: React.FC = () => {
  const [teams, setTeams] = useState<any[]>([])
  const [teamId, setTeamId] = useState<string>('')
  const [positions, setPositions] = useState<string[]>([])
  const [maxValue, setMaxValue] = useState('')
  const [minIndex, setMinIndex] = useState('')
  const [maxAge, setMaxAge] = useState('')
  const [data, setData] = useState<Response | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sortByCoverage, setSortByCoverage] = useState(false)

  // A brief can be impossible, and the form is where that should be caught.
  // The index is a 0-100 scale and the budget is written in millions; typed
  // without units, "10000000" in the index field asks for a player ten
  // million times better than the best there is. The search still answers -
  // every player fails that one criterion, so every player comes back as a
  // near miss - which is the mechanism working and the form failing.
  const problems = useMemo(() => {
    const out: string[] = []
    const idx = Number(minIndex)
    if (minIndex && (!Number.isFinite(idx) || idx < 0 || idx > 100))
      out.push('The performance index runs 0 to 100.')
    const age = Number(maxAge)
    if (maxAge && (!Number.isFinite(age) || age < 14 || age > 50))
      out.push('An age limit outside 14-50 will not narrow anything.')
    const val = Number(maxValue)
    if (maxValue && (!Number.isFinite(val) || val <= 0))
      out.push('The budget is written in millions of euros: 40 means €40M.')
    return out
  }, [minIndex, maxAge, maxValue])

  useEffect(() => {
    api.teams.getAll({ limit: 100 })
      .then((rows: any[]) => {
        const clubs = (rows || []).filter((t) => t.teamType !== 'national')
        setTeams(clubs)
        if (clubs[0]) setTeamId(String(clubs[0].id))
      })
      .catch((e) => console.error('Teams load failed:', e))
  }, [])

  const run = useCallback(async () => {
    if (!teamId) return
    setBusy(true); setError(null)
    try {
      const res = await api.matches.searchForTeam({
        team_id: teamId,
        positions: positions.length ? positions : undefined,
        max_market_value: maxValue ? Number(maxValue) * 1_000_000 : undefined,
        min_performance_index: minIndex ? Number(minIndex) : undefined,
        max_age: maxAge ? Number(maxAge) : undefined,
        limit: 20,
      })
      setData(res)
    } catch (e: any) {
      console.error('Search failed:', e)
      setError('The search could not be run. Check the backend is reachable.')
    } finally {
      setBusy(false)
    }
  }, [teamId, positions, maxValue, minIndex, maxAge])

  const toggle = (p: string) =>
    setPositions((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]))

  // Not a detail: when every row is a near miss, the gold bars stop marking
  // the exception and the list reads as a normal answer to a brief nobody met.
  const allNearMiss = useMemo(
    () => !!data && data.results.length > 0 && data.results.every((r) => r.near_miss),
    [data],
  )

  // A caveat that applies to every row is not a property of any row. If no
  // player in the source carries a date of birth, saying so eighteen times
  // turns a real limitation into wallpaper; it belongs once, at the top.
  const universalGaps = useMemo(() => {
    if (!data || data.results.length === 0) return []
    return data.results[0].criteria
      .filter((c) => !c.assessed)
      .filter((c) => data.results.every(
        (r) => r.criteria.some((x) => x.name === c.name && !x.assessed)))
  }, [data])

  const rows = useMemo(() => {
    if (!data) return []
    if (!sortByCoverage) return data.results
    // Rank order is preserved inside each coverage band, so sorting by
    // coverage reorders what the scout trusts, not what the model scored.
    return [...data.results].sort((a, b) => b.coverage - a.coverage || a.rank - b.rank)
  }, [data, sortByCoverage])

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,2.2fr)] gap-10">
        {/* ---------------------------------------------------- the brief */}
        <div>
          <h2 className="font-display text-2xl m-0 pb-3 border-b border-rule">The brief</h2>

          <div className="mt-5">
            <label htmlFor="club" className="label block mb-2">Club</label>
            <select
              id="club"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              className="bg-paper-card border border-rule-strong px-3.5 py-3 text-sm w-full focus:border-ink"
              style={{ minHeight: 44 }}
            >
              {teams.map((t) => (
                <option key={t.id} value={String(t.id)}>{t.name} — {t.league}</option>
              ))}
            </select>
          </div>

          <div className="mt-5">
            <div className="label mb-2">Positions</div>
            <div className="flex flex-wrap gap-1.5">
              {POSITIONS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => toggle(p)}
                  className={`font-label text-label font-semibold uppercase px-2.5 py-2 border ${
                    positions.includes(p)
                      ? 'bg-ink text-paper border-ink'
                      : 'border-rule-strong text-ink-soft hover:border-ink hover:text-ink'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-ink-faint max-w-read">
              {positions.length
                ? 'Only these positions are searched.'
                : "None picked — the club's own declared needs are used."}
            </p>
          </div>

          <div className="mt-5 grid grid-cols-3 gap-3">
            <div>
              <label htmlFor="budget" className="label block mb-2">Budget €M</label>
              <input id="budget" type="number" min={0} step={1} value={maxValue}
                onChange={(e) => setMaxValue(e.target.value)} placeholder="any"
                className="w-full bg-paper-card border border-rule-strong px-3 py-3 text-sm
                           placeholder:text-ink-faint focus:border-ink tabular"
                style={{ minHeight: 44 }} />
              <div className="label mt-1 text-ink-faint">
                {maxValue && Number(maxValue) > 0
                  ? `= €${Number(maxValue).toFixed(1)}M`
                  : 'millions'}
              </div>
            </div>
            <div>
              <label htmlFor="level" className="label block mb-2">Min index</label>
              <input id="level" type="number" min={0} max={100} step={1} value={minIndex}
                onChange={(e) => setMinIndex(e.target.value)} placeholder="any"
                className="w-full bg-paper-card border border-rule-strong px-3 py-3 text-sm
                           placeholder:text-ink-faint focus:border-ink tabular"
                style={{ minHeight: 44 }} />
              <div className="label mt-1 text-ink-faint">0–100</div>
            </div>
            <div>
              <label htmlFor="age" className="label block mb-2">Max age</label>
              <input id="age" type="number" min={14} max={50} step={1} value={maxAge}
                onChange={(e) => setMaxAge(e.target.value)} placeholder="any"
                className="w-full bg-paper-card border border-rule-strong px-3 py-3 text-sm
                           placeholder:text-ink-faint focus:border-ink tabular"
                style={{ minHeight: 44 }} />
              <div className="label mt-1 text-ink-faint">years</div>
            </div>
          </div>

          {problems.length > 0 && (
            <ul className="mt-3 max-w-read space-y-1">
              {problems.map((t, i) => (
                <li key={i} className="text-xs text-loss">{t}</li>
              ))}
            </ul>
          )}

          <p className="mt-2 text-xs text-ink-faint max-w-read">
            This source carries no dates of birth, so an age limit will exclude
            nobody until one does.
          </p>

          <button
            type="button"
            onClick={run}
            disabled={busy || !teamId || problems.length > 0}
            className="mt-6 w-full font-label text-label font-semibold uppercase px-4 py-3
                       bg-ink text-paper inline-flex items-center justify-center gap-2
                       hover:bg-field-dark disabled:opacity-40"
            style={{ minHeight: 44 }}
          >
            <Search className="w-4 h-4" aria-hidden="true" />
            {busy ? 'Searching…' : 'Search'}
          </button>

          {error && <p className="mt-4 text-sm text-loss max-w-read">{error}</p>}
        </div>

        {/* -------------------------------------------------- the results */}
        <div>
          {!data ? (
            <div className="border border-dashed border-rule-strong p-8 max-w-read">
              <h3 className="label mb-2">No search run yet</h3>
              <p className="text-sm text-ink-soft">
                Pick a club and press Search. Leave the brief empty and Kumü
                uses what the club has declared it needs.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-baseline justify-between gap-4 pb-3 border-b border-rule-strong">
                <h2 className="font-display text-2xl m-0">
                  For {data.team.name}{' '}
                  <span className="text-ink-faint tabular">({data.results.length})</span>
                </h2>
                <button
                  type="button"
                  onClick={() => setSortByCoverage((v) => !v)}
                  className="label text-ink-soft hover:text-ink underline underline-offset-4"
                >
                  {sortByCoverage ? 'Sort by rank' : 'Sort by coverage'}
                </button>
              </div>

              {allNearMiss && (
                <div className="mt-4 border border-dashed border-flag p-5 max-w-read">
                  <h3 className="label text-flag-mark mb-2">Nobody meets this brief</h3>
                  <p className="text-sm text-ink-soft">
                    Every player below fails the same single condition —{' '}
                    {data.results[0].missed}. They are shown because each one
                    fails only that, and a brief nobody meets is worth saying
                    out loud rather than returning as if it were a result.
                  </p>
                </div>
              )}

              <p className="mt-3 max-w-read text-xs text-ink-faint">{data.basis}</p>

              {universalGaps.length > 0 && (
                <p className="mt-2 max-w-read text-xs text-ink-faint">
                  Unassessed for every player here:{' '}
                  {universalGaps.map((c) => c.detail || c.name.toLowerCase()).join(' ')}
                </p>
              )}

              {data.results.length === 0 && (
                <p className="mt-6 text-sm text-ink-soft max-w-read">
                  Nobody in the readable population matches this brief. Widen it,
                  or clear the positions to use the club&apos;s declared needs.
                </p>
              )}

              <div className="mt-2">
                {rows.map((r, i) => {
                  // Per-row gaps, minus the ones already stated once above.
                  const missing = r.criteria.filter(
                    (c) => !c.assessed && !universalGaps.some((u) => u.name === c.name))
                  // Near misses sort after clean matches, so the score stops
                  // falling at the boundary and starts again. Unannounced,
                  // that reads as a broken sort rather than a second list.
                  const opensNearMisses =
                    !sortByCoverage && r.near_miss && (i === 0 || !rows[i - 1].near_miss)
                  return (
                    <React.Fragment key={r.player.id}>
                    {opensNearMisses && (
                      <div className="mt-8 mb-2 pt-5 border-t-2 border-flag">
                        <div className="label text-flag-mark">Near misses</div>
                        <p className="mt-1 max-w-read text-sm text-ink-soft">
                          Each of these fails exactly one condition of the brief
                          and nothing else. They are ranked among themselves, so
                          the score picks up again here rather than continuing
                          down.
                        </p>
                      </div>
                    )}
                    <div
                      className={`py-4 border-b border-rule last:border-0 ${
                        r.near_miss ? 'border-l-2 border-l-flag pl-4' : ''
                      }`}
                    >
                      <div className="flex items-baseline gap-4">
                        <div className="label text-ink-faint tabular w-6 shrink-0">
                          {String(r.rank).padStart(2, '0')}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-ink">{r.player.name}</div>
                          <div className="label mt-0.5">
                            {describe(r.player.position, r.player.nationality,
                                      r.player.current_team)}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="font-display font-bold text-xl tabular leading-none">
                            {r.score.overall.toFixed(1)}
                          </div>
                          <div className="label mt-1">
                            {Math.round(r.coverage * 4)} of 4 criteria
                          </div>
                        </div>
                        <div className="text-right shrink-0 w-24 hidden sm:block">
                          <div className="tabular text-sm">
                            {typeof r.player.market_value === 'number'
                              ? money(r.player.market_value)
                              : '—'}
                          </div>
                          <div className="label mt-1">
                            index{' '}
                            {typeof r.player.performance_index === 'number'
                              ? r.player.performance_index.toFixed(1)
                              : '—'}
                          </div>
                        </div>
                      </div>

                      {r.near_miss && !allNearMiss && (
                        <p className="mt-2 ml-10 text-xs text-flag">
                          Kept despite being {r.missed} — it is the only thing
                          in the brief this player fails.
                        </p>
                      )}

                      {missing.length > 0 && (
                        <p className="mt-2 ml-10 text-xs text-ink-faint max-w-read">
                          Not assessed:{' '}
                          {missing.map((c) => c.detail || c.name.toLowerCase()).join(' ')}
                        </p>
                      )}
                    </div>
                    </React.Fragment>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default ClubSearch
