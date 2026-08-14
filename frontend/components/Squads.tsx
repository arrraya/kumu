'use client'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Search, UserPlus, UserMinus, Users, Shield } from 'lucide-react'
import { api } from '@/lib/api'

/**
 * Squad builder.
 *
 * Squads live in a membership relation shared by three sources: national sides
 * come from the source data, clubs are assembled here, and a provider API can
 * fill the same table later. Signing a player moves him out of any other club
 * squad, so "who does this club already have" keeps meaning something — which
 * is what the scouting report leans on to judge whether a signing is an upgrade.
 */

const money = (v: number | null | undefined) =>
  typeof v === 'number' ? `€${(v / 1_000_000).toFixed(1)}M` : '—'

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

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Squads</h1>
        <p className="text-gray-600 mt-1">
          Build a club squad to see whether a signing actually improves it.
          <span className="text-gray-400">
            {' '}National squads come from the source data and are read-only.
          </span>
        </p>
      </div>

      {loading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">Loading teams…</div>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <label className="text-sm font-medium text-gray-700 block mb-2">Team</label>
            <select
              value={teamId ?? ''}
              onChange={(e) => setTeamId(Number(e.target.value))}
              className="border rounded-md px-3 py-2 text-sm w-full sm:w-80"
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
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4">
                <div className="text-2xl font-bold">{stats.squad_size ?? 0}</div>
                <div className="text-sm text-gray-600">Squad size</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <div className="text-2xl font-bold">{money(stats.total_market_value)}</div>
                <div className="text-sm text-gray-600">Squad value</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                {/* National sides carry no transfer budget, so the overrun
                    warning does not apply to them — it fired for every one of
                    them because their budget is zero by construction. */}
                <div className={`text-2xl font-bold ${
                  !isNational && (stats.total_market_value || 0) > (stats.budget_remaining || 0)
                    ? 'text-red-600' : ''}`}>
                  {isNational ? '—' : money(stats.budget_remaining)}
                </div>
                <div className="text-sm text-gray-600">
                  {isNational ? 'No transfer budget' : 'Budget'}
                </div>
                {!isNational &&
                  (stats.total_market_value || 0) > (stats.budget_remaining || 0) && (
                    <div className="text-xs text-red-600 mt-1">Squad exceeds budget</div>
                  )}
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <div className="text-2xl font-bold">
                  {Object.keys(stats.position_distribution || {}).length}
                </div>
                <div className="text-sm text-gray-600">Positions covered</div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
              <h3 className="font-semibold mb-2 flex items-center gap-2">
                <Users className="w-4 h-4" />
                {team?.name} squad ({squad.length})
              </h3>
              {isNational && (
                <p className="text-xs text-gray-500 mb-4">
                  Players with enough minutes in the source tournament, not the full
                  call-up: goalkeepers and low-minute squad members are not included.
                </p>
              )}

              {squad.length === 0 ? (
                <p className="text-sm text-gray-500">
                  {isNational
                    ? 'No players recorded for this national side.'
                    : 'Empty squad — sign players from the panel on the right.'}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-gray-600 border-b">
                      <tr>
                        <th className="text-left py-2">Player</th>
                        <th className="text-left py-2">Pos</th>
                        <th className="text-right py-2">Index</th>
                        <th className="text-right py-2">Value</th>
                        {!isNational && <th className="text-right py-2"></th>}
                      </tr>
                    </thead>
                    <tbody>
                      {squad.map((p) => (
                        <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                          <td className="py-2">
                            <div className="font-medium text-gray-900">{p.name}</div>
                            <div className="text-xs text-gray-500">{p.nationality}</div>
                          </td>
                          <td className="py-2 text-gray-600">{p.position}</td>
                          <td className="py-2 text-right">
                            {typeof p.performance_index === 'number'
                              ? p.performance_index.toFixed(1)
                              : '—'}
                          </td>
                          <td className="py-2 text-right font-medium">{money(p.market_value)}</td>
                          {!isNational && (
                            <td className="py-2 text-right">
                              <button
                                onClick={() => release(p.id)}
                                disabled={busy}
                                className="px-2 py-1 text-xs rounded bg-gray-200 text-gray-700 inline-flex items-center gap-1 disabled:opacity-40"
                              >
                                <UserMinus className="w-3 h-3" /> Release
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

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <Shield className="w-4 h-4" /> Sign a player
              </h3>

              {isNational ? (
                <p className="text-sm text-gray-500">
                  National squads reflect the source data and cannot be edited.
                  Pick a club to build a squad.
                </p>
              ) : (
                <>
                  <div className="relative mb-3">
                    <Search className="w-4 h-4 text-gray-400 absolute left-2 top-2.5" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search a player…"
                      className="w-full pl-8 pr-3 py-2 border rounded-md text-sm"
                    />
                  </div>

                  {results.length === 0 && search.trim() && (
                    <p className="text-sm text-gray-500">No players match that search.</p>
                  )}

                  <div className="space-y-2">
                    {results.map((p) => (
                      <div key={p.id} className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-gray-900 truncate">{p.name}</div>
                          <div className="text-xs text-gray-500">
                            {p.position} • {money(p.marketValue)}
                          </div>
                        </div>
                        <button
                          onClick={() => sign(p.id)}
                          disabled={busy || inSquad(p.id)}
                          className="px-2 py-1 text-xs rounded bg-green-600 text-white inline-flex items-center gap-1 disabled:opacity-40 shrink-0"
                        >
                          <UserPlus className="w-3 h-3" />
                          {inSquad(p.id) ? 'In squad' : 'Sign'}
                        </button>
                      </div>
                    ))}
                  </div>

                  <p className="text-xs text-gray-400 mt-4">
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
