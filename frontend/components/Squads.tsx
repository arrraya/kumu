'use client'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Search, UserPlus, UserMinus } from 'lucide-react'
import { api } from '@/lib/api'
import { valueMark, valueTitle, money } from '@/lib/provenance'

/**
 * Squad builder.
 *
 * Squads live in a membership relation shared by three sources: national sides
 * come from the source data, clubs are assembled here, and a provider API can
 * fill the same table later. Signing a player moves him out of any other club
 * squad, so "who does this club already have" keeps meaning something — which
 * is what the scouting report leans on to judge whether a signing is an upgrade.
 *
 * CANCHA. This screen is the escape hatch in action: a squad list has no
 * geography, so it uses the document grid, not the zone grid. Same palette,
 * same type, different frame — which is the whole rule.
 *
 * The local money() helper moved to lib/provenance so the squad table and the
 * dashboard cannot drift apart on how a value is written or marked.
 */

const Squads: React.FC = () => {
  const [teams, setTeams] = useState<any[]>([])
  const [teamId, setTeamId] = useState<number | null>(null)
  const [squad, setSquad] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const [results, setResults] = useState<any[]>([])

  const team = useMemo(() => teams.find((t) => t.id === teamId), [teams, teamId])
  const clubs = useMemo(() => teams.filter((t) => t.teamType !== 'national'), [teams])
  const nations = useMemo(() => teams.filter((t) => t.teamType === 'national'), [teams])
  const isNational = team?.teamType === 'national'

  useEffect(() => {
    const run = async () => {
      try {
        const data = await api.teams.getAll({ limit: 100 })
        setTeams(data || [])
        const firstClub = (data || []).find((t: any) => t.teamType !== 'national')
        if (firstClub) setTeamId(firstClub.id)
      } catch (e) {
        console.error('Teams load failed:', e)
      } finally {
        setLoading(false)
      }
    }
    run()
  }, [])

  const loadSquad = useCallback(async (id: number) => {
    try {
      const [squadData, statsData] = await Promise.all([
        api.squads.get(id),
        api.squads.statistics(id),
      ])
      setSquad(squadData?.players || [])
      setStats(statsData)
    } catch (e) {
      console.error('Squad load failed:', e)
      setSquad([])
      setStats(null)
    }
  }, [])

  useEffect(() => {
    if (teamId) loadSquad(teamId)
  }, [teamId, loadSquad])

  useEffect(() => {
    if (!search.trim()) {
      setResults([])
      return
    }
    const t = setTimeout(async () => {
      try {
        const data = await api.players.getAll({ search, limit: 8 })
        setResults(data || [])
      } catch (e) {
        console.error('Player search failed:', e)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [search])

  const sign = async (playerId: number) => {
    if (!teamId || busy) return
    try {
      setBusy(true)
      await api.squads.add(teamId, playerId)
      await loadSquad(teamId)
      setSearch('')
    } catch (e) {
      console.error('Signing failed:', e)
    } finally {
      setBusy(false)
    }
  }

  const release = async (playerId: number) => {
    if (!teamId || busy) return
    try {
      setBusy(true)
      await api.squads.remove(teamId, playerId)
      await loadSquad(teamId)
    } catch (e) {
      console.error('Release failed:', e)
    } finally {
      setBusy(false)
    }
  }

  const inSquad = (id: number) => squad.some((p) => p.id === id)

  const overBudget =
    !isNational && (stats?.total_market_value || 0) > (stats?.budget_remaining || 0)

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="masthead">
        <div className="label text-clay-ink mb-3">Squads · who the club already has</div>
        <h1 className="font-display text-4xl md:text-5xl leading-none m-0">Squads</h1>
        <p className="mt-4 max-w-read text-lg text-ink-soft">
          Build a club squad to see whether a signing actually improves it.
          <span className="text-ink-faint">
            {' '}National squads come from the source data and are read-only.
          </span>
        </p>
      </div>

      {loading ? (
        <div className="panel mt-8 text-center text-ink-faint">Loading teams…</div>
      ) : (
        <>
          <div className="mt-8">
            <label htmlFor="team" className="label block mb-2">Team</label>
            <select
              id="team"
              value={teamId ?? ''}
              onChange={(e) => setTeamId(Number(e.target.value))}
              className="bg-paper-card border border-rule-strong px-3.5 py-3 text-sm w-full sm:w-96
                         focus:border-ink"
              style={{ minHeight: 44 }}
            >
              <optgroup label="Clubs">
                {clubs.map((t) => (
                  <option key={t.id} value={t.id}>{t.name} — {t.league}</option>
                ))}
              </optgroup>
              <optgroup label="National teams (read-only)">
                {nations.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </optgroup>
            </select>
          </div>

          {stats && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mt-8">
              <div className="border-t-2 border-ink pt-3">
                <div className="figure">{stats.squad_size ?? 0}</div>
                <div className="label mt-2">Squad size</div>
              </div>
              <div className="border-t-2 border-ink pt-3">
                {/* An empty squad is worth exactly nothing, and nothing about
                    that was estimated. A mark that is always on says nothing. */}
                <div className={`figure ${stats.squad_size ? 'is-estimated' : ''}`}>
                  {money(stats.total_market_value)}
                </div>
                <div className="label mt-2">Squad value</div>
              </div>
              <div className="border-t-2 border-ink pt-3">
                {/* National sides carry no transfer budget, so the overrun
                    warning does not apply to them — it fired for every one of
                    them because their budget is zero by construction. */}
                <div className={`figure ${overBudget ? 'text-loss' : ''}`}>
                  {isNational ? '—' : money(stats.budget_remaining)}
                </div>
                <div className="label mt-2">
                  {isNational ? 'No transfer budget' : 'Budget'}
                </div>
                {overBudget && (
                  <div className="text-xs text-loss mt-1">Squad exceeds budget</div>
                )}
              </div>
              <div className="border-t-2 border-ink pt-3">
                <div className="figure">
                  {Object.keys(stats.position_distribution || {}).length}
                </div>
                <div className="label mt-2">Positions covered</div>
              </div>
            </div>
          )}

          <div className="section grid grid-cols-1 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-10">
            <div>
              <h2 className="font-display text-2xl m-0 pb-3 border-b border-rule">
                {team?.name} squad <span className="text-ink-faint tabular">({squad.length})</span>
              </h2>
              {isNational && (
                <p className="mt-3 max-w-read text-sm text-ink-soft">
                  Players with enough minutes in the source tournament, not the full
                  call-up: goalkeepers and low-minute squad members are not included.
                </p>
              )}

              {squad.length === 0 ? (
                <p className="mt-5 text-sm text-ink-faint">
                  {isNational
                    ? 'No players recorded for this national side.'
                    : 'Empty squad — sign players from the panel on the right.'}
                </p>
              ) : (
                <div className="overflow-x-auto mt-2">
                  <table className="w-full text-sm" style={{ minWidth: 520 }}>
                    <thead>
                      <tr>
                        <th scope="col" className="label text-left py-3 border-b border-rule-strong">Player</th>
                        <th scope="col" className="label text-left py-3 border-b border-rule-strong">Pos</th>
                        <th scope="col" className="label text-right py-3 border-b border-rule-strong">Index</th>
                        <th scope="col" className="label text-right py-3 border-b border-rule-strong">Value</th>
                        {!isNational && <th scope="col" className="border-b border-rule-strong"><span className="sr-only">Actions</span></th>}
                      </tr>
                    </thead>
                    <tbody>
                      {squad.map((p) => (
                        <tr key={p.id} className="border-b border-rule last:border-0 hover:bg-paper-sunk">
                          <td className="py-3">
                            <div className="font-medium text-ink">{p.name}</div>
                            <div className="label mt-0.5">{p.nationality}</div>
                          </td>
                          <td className="py-3 text-ink-soft">{p.position}</td>
                          <td className="py-3 text-right font-display font-bold text-base tabular">
                            {typeof p.performance_index === 'number'
                              ? p.performance_index.toFixed(1)
                              : '—'}
                          </td>
                          <td className={`py-3 text-right tabular ${valueMark(p)}`} title={valueTitle(p)}>
                            {money(p.market_value)}
                          </td>
                          {!isNational && (
                            <td className="py-3 text-right">
                              <button
                                type="button"
                                onClick={() => release(p.id)}
                                disabled={busy}
                                className="font-label text-label font-semibold uppercase px-3 py-2
                                           border border-rule-strong text-ink-soft inline-flex items-center gap-1.5
                                           hover:border-ink hover:text-ink disabled:opacity-40"
                              >
                                <UserMinus className="w-3.5 h-3.5" aria-hidden="true" /> Release
                              </button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div>
              <h2 className="font-display text-2xl m-0 pb-3 border-b border-rule">Sign a player</h2>

              {isNational ? (
                <p className="mt-5 max-w-read text-sm text-ink-soft">
                  National squads reflect the source data and cannot be edited.
                  Pick a club to build a squad.
                </p>
              ) : (
                <>
                  <div className="relative mt-5 mb-4">
                    <label htmlFor="player-search" className="sr-only">Search a player</label>
                    <Search className="w-4 h-4 text-ink-faint absolute left-3 top-3.5" aria-hidden="true" />
                    <input
                      id="player-search"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search a player…"
                      className="w-full bg-paper-card border border-rule-strong pl-9 pr-3 py-3 text-sm
                                 placeholder:text-ink-faint focus:border-ink"
                      style={{ minHeight: 44 }}
                    />
                  </div>

                  {results.length === 0 && search.trim() && (
                    <p className="text-sm text-ink-faint">No players match that search.</p>
                  )}

                  <div>
                    {results.map((p) => (
                      <div key={p.id}
                        className="flex items-center justify-between gap-3 py-3 border-b border-rule last:border-0">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-ink truncate">{p.name}</div>
                          <div className="label mt-0.5">
                            {p.position} • <span className={valueMark(p)}>{money(p.marketValue)}</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => sign(p.id)}
                          disabled={busy || inSquad(p.id)}
                          className="font-label text-label font-semibold uppercase px-3 py-2 shrink-0
                                     bg-ink text-paper inline-flex items-center gap-1.5
                                     hover:bg-field-dark disabled:opacity-40"
                        >
                          <UserPlus className="w-3.5 h-3.5" aria-hidden="true" />
                          {inSquad(p.id) ? 'In squad' : 'Sign'}
                        </button>
                      </div>
                    ))}
                  </div>

                  <p className="mt-5 max-w-read text-sm text-ink-soft">
                    Signing moves the player out of any other club squad.
                  </p>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default Squads
