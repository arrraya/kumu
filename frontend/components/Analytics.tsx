'use client'
import React, { useEffect, useMemo, useState } from 'react'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '@/lib/api'

/**
 * Player comparison built entirely from pipeline data.
 * Percentiles are computed against players in the SAME position, so a striker
 * is measured against strikers and a defender against defenders.
 */

const METRICS = [
  { path: ['passing', 'completion_rate'], label: 'Pass completion', fmt: (v: number) => `${(v * 100).toFixed(1)}%` },
  { path: ['passing', 'key_passes_per_90'], label: 'Key passes', fmt: (v: number) => v.toFixed(2) },
  { path: ['passing', 'progressive_passes_per_90'], label: 'Progressive passes', fmt: (v: number) => v.toFixed(2) },
  { path: ['shooting', 'goals_per_90'], label: 'Goals', fmt: (v: number) => v.toFixed(2) },
  { path: ['shooting', 'assists_per_90'], label: 'Assists', fmt: (v: number) => v.toFixed(2) },
  { path: ['shooting', 'shots_per_90'], label: 'Shots', fmt: (v: number) => v.toFixed(2) },
  { path: ['defensive', 'tackles_per_90'], label: 'Tackles', fmt: (v: number) => v.toFixed(2) },
  { path: ['defensive', 'interceptions_per_90'], label: 'Interceptions', fmt: (v: number) => v.toFixed(2) },
]

const getMetric = (player: any, path: string[]): number | null => {
  const v = path.reduce((acc: any, k) => (acc ? acc[k] : undefined), player?.metrics)
  return typeof v === 'number' ? v : null
}

const PlayerPicker: React.FC<{
  label: string; players: any[]; value: any; onChange: (p: any) => void; color: string
}> = ({ label, players, value, onChange, color }) => {
  const [query, setQuery] = useState('')
  const matches = useMemo(() => {
    if (!query.trim()) return []
    const q = query.toLowerCase()
    return players.filter((p) => p.name?.toLowerCase().includes(q)).slice(0, 6)
  }, [query, players])

  return (
    <div className="bg-white border border-rule rounded-sm p-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-sm font-medium text-ink-soft">{label}</span>
      </div>

      {value ? (
        <div>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-lg font-bold text-ink">{value.name}</div>
              <div className="text-sm text-ink-soft">
                {value.position} • {value.nationality} • {typeof value.marketValue === 'number' ? `€${(value.marketValue / 1e6).toFixed(1)}M` : 'value n/a'}
              </div>
              <div className="text-sm text-ink-faint mt-1">
                Index: {value.performanceIndex?.value?.toFixed(1) ?? 'n/a'}
                {value.performance_history?.length ? ` • ${value.performance_history.length} matches` : ''}
              </div>
              {/* Without an index the value shown is a floor estimate, not a
                  reading of this player's output — say so rather than letting
                  the figure look as solid as everyone else's. */}
              {!value.performanceIndex?.value && (
                <div className="text-xs text-amber-700 mt-1">
                  Too few matches for an index — value is a floor estimate
                </div>
              )}
            </div>
            <button onClick={() => { onChange(null); setQuery('') }}
              className="text-xs text-ink-faint hover:text-gray-800">change</button>
          </div>
        </div>
      ) : (
        <div className="relative">
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a player…"
            className="w-full border rounded-md px-3 py-2 text-sm" />
          {matches.length > 0 && (
            <div className="absolute z-10 left-0 right-0 mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-y-auto">
              {matches.map((p) => (
                <button key={p.id} onClick={() => { onChange(p); setQuery('') }}
                  className="w-full text-left px-3 py-2 hover:bg-gray-50 text-sm">
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-ink-faint">{p.position} • {p.nationality}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const Analytics: React.FC = () => {
  const [players, setPlayers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [a, setA] = useState<any>(null)
  const [b, setB] = useState<any>(null)

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true)
        const data = await api.players.getAll({ limit: 500 })
        setPlayers(data || [])
      } catch (e) {
        console.error('Analytics load failed:', e)
      } finally { setLoading(false) }
    }
    run()
  }, [])

  // Percentile of a player's metric among peers in the same position
  const percentile = (player: any, path: string[]): number | null => {
    const value = getMetric(player, path)
    if (value === null) return null
    const peers = players
      .filter((p) => p.position === player.position)
      .map((p) => getMetric(p, path))
      .filter((v): v is number => v !== null)
    if (peers.length < 5) return null
    const below = peers.filter((v) => v < value).length
    return Math.round((below / peers.length) * 100)
  }

  const radarData = useMemo(() => {
    if (!a) return []
    return METRICS.map((m) => ({
      metric: m.label,
      A: percentile(a, m.path) ?? 0,
      B: b ? (percentile(b, m.path) ?? 0) : 0,
    }))
  }, [a, b, players])

  const trendData = useMemo(() => {
    const ha = a?.performance_history || []
    const hb = b?.performance_history || []
    const len = Math.max(ha.length, hb.length)
    return Array.from({ length: len }, (_, i) => ({
      label: `M${i + 1}`,
      A: ha[i]?.rating != null ? ha[i].rating * 10 : null,
      B: hb[i]?.rating != null ? hb[i].rating * 10 : null,
    }))
  }, [a, b])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="font-display text-4xl text-ink leading-tight">Player comparison</h1>
        <p className="mt-2 max-w-read text-ink-soft">
          Every figure is measured from match events. Percentiles rank the
          player against others in the same position, where 50 is the typical
          player for that role.
        </p>
      </div>

      {loading ? (
        <div className="bg-white border border-rule rounded-sm p-8 text-center text-ink-faint">Loading players…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <PlayerPicker label="Player A" players={players} value={a} onChange={setA} color="#0F2E22" />
            <PlayerPicker label="Player B (optional)" players={players} value={b} onChange={setB} color="#1A7A4C" />
          </div>

          {!a ? (
            <div className="bg-white border border-rule rounded-sm p-8 text-center text-ink-faint">
              Pick a player to see their statistical profile.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
                <div className="bg-white border border-rule rounded-sm p-6">
                  <h3 className="font-semibold mb-4">Percentile profile</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="#DCE4DF" />
                      <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10 }} />
                      <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9 }} />
                      <Radar name={a.name} dataKey="A" stroke="#0F2E22" fill="#0F2E22" fillOpacity={0.07} strokeWidth={2} />
                      {b && <Radar name={b.name} dataKey="B" stroke="#1A7A4C" fill="#1A7A4C"
                        fillOpacity={0.18} strokeDasharray="4 3" strokeWidth={2} />}
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                <div className="bg-white border border-rule rounded-sm p-6 overflow-x-auto">
                  <h3 className="font-semibold mb-4">Raw metrics</h3>
                  <table className="w-full text-sm">
                    <thead className="text-ink-soft">
                      <tr className="border-b">
                        <th className="text-left py-2">Metric</th>
                        <th className="text-right py-2 text-ink">{a.name.split(' ').slice(-1)[0]}</th>
                        {b && <th className="text-right py-2 text-field">{b.name.split(' ').slice(-1)[0]}</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {METRICS.map((m) => {
                        const va = getMetric(a, m.path)
                        const vb = b ? getMetric(b, m.path) : null
                        const pa = percentile(a, m.path)
                        const pb = b ? percentile(b, m.path) : null
                        return (
                          <tr key={m.label} className="border-b last:border-0">
                            <td className="py-2 text-ink-soft">{m.label}</td>
                            <Cell value={va === null ? null : m.fmt(va)} pct={pa} />
                            {b && (
                              <Cell value={vb === null ? null : m.fmt(vb)} pct={pb} />
                            )}
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {trendData.length > 0 && (
                <div className="bg-white border border-rule rounded-sm p-6">
                  <h3 className="font-semibold mb-4">Match-by-match rating</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <LineChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#DCE4DF" />
                      <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} domain={['dataMin - 5', 'dataMax + 5']} />
                      <Tooltip />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="A" name={a.name} stroke="#0F2E22"
                        strokeWidth={2} dot={{ r: 3 }} connectNulls />
                      {b && <Line type="monotone" dataKey="B" name={b.name} stroke="#1A7A4C" strokeDasharray="4 3"
                        strokeWidth={2} dot={{ r: 3 }} connectNulls />}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

/**
 * A measurement and where it ranks, as two readings rather than one string.
 *
 * These used to share a cell as "86.0% · p73": two different scales joined by
 * a dot, so neither could be scanned down its column. The value stays tabular
 * and the rank becomes a bar, which is what a percentile is for.
 */
const Cell: React.FC<{ value: string | null; pct: number | null }> = ({ value, pct }) => (
  <td className="py-2.5 text-right align-top">
    {value === null ? (
      <span className="text-ink-faint">n/a</span>
    ) : (
      <>
        <div className="tabular text-ink">{value}</div>
        {pct !== null && (
          <div className="mt-1 flex items-center justify-end gap-2">
            <span className="w-16 h-1 bg-paper-sunk">
              <span
                className="block h-full bg-field"
                style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
              />
            </span>
            <span className="w-6 text-xs text-ink-faint tabular">{pct}</span>
          </div>
        )}
      </>
    )}
  </td>
)

export default Analytics
