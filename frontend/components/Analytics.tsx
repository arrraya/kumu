'use client'
import React, { useEffect, useMemo, useState } from 'react'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '@/lib/api'
import { valueMark, valueTitle } from '@/lib/provenance'
import { formatMoney } from '@/lib/money'
import { paddedDomain, wholeTick } from '@/lib/axis'
import PitchMap, { MAP_NOTE, MapViewToggle } from './PitchMap'

/**
 * Player comparison built entirely from pipeline data.
 * Percentiles are computed against players in the SAME position, so a striker
 * is measured against strikers and a defender against defenders.
 *
 * CANCHA. Three things changed with the visual language, and none of them is
 * decoration:
 *
 *  - The pitch map moved from a component buried in the scouting report to the
 *    first figure on this screen. Kumü's differentiation is spatial; the old
 *    layout hid it behind two charts that any provider also ships.
 *  - The percentile rows replaced the "Raw metrics" table. The table and the
 *    bars were showing the same two numbers in two places, and the table lost
 *    every comparison it was meant to serve: a value and a rank on different
 *    scales cannot be scanned down one column.
 *  - A is clay and B is slate everywhere, including inside the pitch map. The
 *    two differ in lightness as well as hue, so the screen holds up printed in
 *    black and white and for a colour-blind reader.
 *  - Every division of horizontal space is now stated in zones rather than in
 *    fractions. The pickers take three columns each, the two halves of a
 *    pitch; the detail takes four against the radar's two, which keeps the
 *    two-to-one the old `minmax(0,1.6fr) minmax(0,1fr)` was reaching for
 *    without inventing a ratio; and two pitch maps sit side by side at three
 *    each, because two heat maps stacked four hundred pixels apart cannot be
 *    compared by eye and that comparison is the whole point of the screen.
 *
 *    Content that fills the width keeps no grid wrapper. A panel occupying
 *    all six zones is the section, and wrapping it in a six-column grid to
 *    say so would be ceremony. `.grid-zones` earns its place where space is
 *    divided, which is the only place a grid decides anything.
 */

const SERIES = {
  a: { stroke: '#C25A3A', ink: '#A6462A', bar: 'bar-a' },
  b: { stroke: '#3A5A7A', ink: '#2F4A66', bar: 'bar-b' },
} as const

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

const spatialOf = (player: any) => player?.spatial_profile ?? player?.spatialProfile ?? null

const PlayerPicker: React.FC<{
  label: string; players: any[]; value: any; onChange: (p: any) => void; series: keyof typeof SERIES
}> = ({ label, players, value, onChange, series }) => {
  const [query, setQuery] = useState('')
  const inputId = `pick-${series}`
  const matches = useMemo(() => {
    if (!query.trim()) return []
    const q = query.toLowerCase()
    return players.filter((p) => p.name?.toLowerCase().includes(q)).slice(0, 6)
  }, [query, players])

  return (
    <div className="bg-paper-card border border-rule p-5">
      <div className="flex items-center gap-2.5 mb-3">
        {/* A square, not a dot: the same mark that keys the bars and the radar. */}
        <span className="w-4 h-2.5 inline-block" style={{ backgroundColor: SERIES[series].stroke }} />
        <span className="label">{label}</span>
      </div>

      {value ? (
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-display text-2xl leading-none">{value.name}</div>
            <div className="mt-2 text-sm text-ink-soft">
              {value.position} • {value.nationality} •{' '}
              {typeof value.marketValue === 'number' ? (
                <span className={`tabular ${valueMark(value)}`} title={valueTitle(value)}>
                  {formatMoney(value.marketValue)}
                </span>
              ) : 'value n/a'}
            </div>
            <div className="mt-1 text-sm text-ink-faint tabular">
              Index: {value.performanceIndex?.value?.toFixed(1) ?? 'n/a'}
              {value.performance_history?.length ? ` • ${value.performance_history.length} matches` : ''}
            </div>
            {/* Without an index the value shown is a floor estimate, not a
                reading of this player's output — say so rather than letting
                the figure look as solid as everyone else's. */}
            {!value.performanceIndex?.value && (
              <div className="mt-2 text-xs text-flag">
                Too few matches for an index — value is a floor estimate
              </div>
            )}
          </div>
          <button type="button" onClick={() => { onChange(null); setQuery('') }}
            className="label hover:text-ink">change</button>
        </div>
      ) : (
        <div className="relative">
          <label htmlFor={inputId} className="sr-only">{label}</label>
          <input id={inputId} value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a player…"
            className="w-full bg-paper border border-rule-strong px-3.5 py-3 text-sm
                       placeholder:text-ink-faint focus:border-ink" />
          {matches.length > 0 && (
            <div className="absolute z-10 left-0 right-0 mt-1 bg-paper-card border border-ink
                            max-h-60 overflow-y-auto">
              {matches.map((p) => (
                <button type="button" key={p.id} onClick={() => { onChange(p); setQuery('') }}
                  className="w-full text-left px-3.5 py-3 hover:bg-paper-sunk border-b border-rule last:border-0">
                  <div className="font-medium text-sm">{p.name}</div>
                  <div className="label mt-0.5">{p.position} • {p.nationality}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * One percentile bar, with its rank spelled out beside it.
 *
 * The number beside the track is not redundant with the bar: an empty track
 * used to mean two different things — ranked last, and not ranked at all —
 * and nothing on screen told them apart. Now a rank of zero draws a sliver and
 * prints 0, while no rank prints an em dash and draws nothing.
 */
const Bar: React.FC<{ pct: number | null; cls: string; label: string }> = ({ pct, cls, label }) => (
  <div className="flex items-center gap-2.5">
    <div className="bar-track flex-1">
      {pct !== null && (
        <span
          className={`${cls} block`}
          role="img"
          aria-label={`${label}: percentile ${pct}`}
          style={{ width: `max(3px, ${Math.max(0, Math.min(100, pct))}%)` }}
        />
      )}
    </div>
    <span className="font-label text-label font-semibold w-7 shrink-0 text-right tabular text-ink-soft">
      {pct === null ? '—' : pct}
    </span>
  </div>
)

/**
 * One metric, both players, as a pair of stacked bars under a shared label.
 *
 * Stacked rather than side by side on purpose: two bars that start from the
 * same left edge are compared by length, which is the one judgement the eye
 * makes accurately without a scale.
 */
const PercentileRow: React.FC<{
  label: string
  valueText: string
  pctA: number | null
  pctB: number | null
  hasB: boolean
}> = ({ label, valueText, pctA, pctB, hasB }) => (
  <div className="flex flex-col gap-1.5">
    <div className="flex items-baseline justify-between gap-4">
      <span className="label text-ink">{label}</span>
      <span className="text-sm text-ink-soft tabular shrink-0">{valueText}</span>
    </div>
    <Bar pct={pctA} cls={SERIES.a.bar} label={label} />
    {hasB && <Bar pct={pctB} cls={SERIES.b.bar} label={label} />}
  </div>
)

const Analytics: React.FC = () => {
  const [players, setPlayers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [a, setA] = useState<any>(null)
  const [b, setB] = useState<any>(null)
  // The view belongs to the screen, not to each map. Two maps shown for
  // comparison have to be showing the same reading, and with a toggle on
  // each one nothing stopped Pedri's involvement being set beside
  // Bellingham's passing - two different questions, answered side by side,
  // presented as an answer to one.
  const [mapView, setMapView] = useState<'touches' | 'flows'>('touches')

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

  const axisFont = { fontFamily: 'Archivo Narrow, Archivo, sans-serif', fontSize: 10, fill: '#5C5F56' }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

      <div className="masthead">
        <div className="label text-clay-ink mb-3">Analytics · percentiles against the position</div>
        <h1 className="font-display text-4xl md:text-5xl leading-none m-0">Player comparison</h1>
        <p className="mt-4 max-w-read text-lg text-ink-soft">
          Every figure is measured from match events. Percentiles rank the
          player against others in the same position, where 50 is the typical
          player for that role.
        </p>
      </div>

      {loading ? (
        <div className="panel mt-8 text-center text-ink-faint">Loading players…</div>
      ) : (
        <>
          {/* gap-5 over the class's gap-3: zones on the pitch are contiguous,
              panels on a page are not. The columns are what the grid decides;
              the gutter belongs to the content sitting in them. */}
          <div className="grid-zones gap-5 mt-8">
            <div className="col-span-6 md:col-span-3">
              <PlayerPicker label="Player A" players={players} value={a} onChange={setA} series="a" />
            </div>
            <div className="col-span-6 md:col-span-3">
              <PlayerPicker label="Player B (optional)" players={players} value={b} onChange={setB} series="b" />
            </div>
          </div>

          {/* The legend for the provenance mark, once per view. A typographic
              device nobody has been taught to read is just a stray underline. */}
          <p className="mt-3 max-w-read text-sm text-ink-soft">
            A figure carrying a <span className="is-estimated">dotted underline</span> was
            estimated from the league anchor, not declared by the club.
          </p>

          {!a ? (
            <div className="panel mt-8 text-center text-ink-faint">
              Pick a player to see their statistical profile.
            </div>
          ) : (
            <>
              {/* HEAD TO HEAD. The index is the answer this screen exists to
                  give, so it is set at display size and nothing on the page
                  competes with it. */}
              <div className="mt-10 grid-zones gap-x-8 gap-y-5 items-end border-b-[3px] border-ink pb-5">
                <h2 className="col-span-6 lg:col-span-4 font-display text-3xl md:text-4xl leading-none m-0">
                  {a.name}
                  {b && <span className="font-normal text-ink-faint"> vs {b.name}</span>}
                </h2>
                <div className="col-span-6 lg:col-span-2 flex gap-8 lg:justify-end">
                  <div className="pl-3.5 border-l-[6px]" style={{ borderColor: SERIES.a.stroke }}>
                    <div className="label">Index A</div>
                    <div className="figure-lg">{a.performanceIndex?.value?.toFixed(1) ?? '—'}</div>
                  </div>
                  {b && (
                    <div className="pl-3.5 border-l-[6px]" style={{ borderColor: SERIES.b.stroke }}>
                      <div className="label">Index B</div>
                      <div className="figure-lg text-ink-soft">{b.performanceIndex?.value?.toFixed(1) ?? '—'}</div>
                    </div>
                  )}
                </div>
              </div>

              {/* The spatial figure first: it is the one reading no other
                  provider ships, and it frames everything below it.

                  Three zones each when there are two players. They used to
                  stack, which put four hundred pixels between two heat maps
                  the reader is meant to compare - and comparing them is the
                  reason both are drawn. */}
              {/* A label for the control, not a heading. Each map is titled
                  with its player, so "Where they play" over them would be the
                  same words twice in two sizes. */}
              <div className="mt-10 flex flex-wrap items-center justify-between gap-4">
                <span className="label">Map view{b ? ' · both players' : ''}</span>
                <MapViewToggle view={mapView} onChange={setMapView} />
              </div>

              <div className="mt-5 grid-zones gap-x-6 gap-y-8">
                <div className={b ? 'col-span-6 lg:col-span-3' : 'col-span-6'}>
                  <PitchMap profile={spatialOf(a)} name={a.name} tone="a"
                    view={mapView} onViewChange={setMapView} note={false} fill />
                </div>
                {b && (
                  <div className="col-span-6 lg:col-span-3">
                    <PitchMap profile={spatialOf(b)} name={b.name} tone="b"
                      view={mapView} onViewChange={setMapView} note={false} fill />
                  </div>
                )}
              </div>

              {/* Once, under both. It describes the reading, and the reading
                  is now the same on both maps by construction. */}
              <p className="mt-4 max-w-read text-sm text-ink-soft">
                {MAP_NOTE[mapView]}
              </p>

              <div className="section grid-zones gap-x-10 gap-y-10">
                <div className="col-span-6 lg:col-span-4">
                  <h3 className="font-display text-2xl m-0 pb-3 border-b border-rule">
                    Percentiles against the position
                  </h3>
                  <div className="mt-5 flex flex-col gap-4">
                    {METRICS.map((m) => {
                      const va = getMetric(a, m.path)
                      const vb = b ? getMetric(b, m.path) : null
                      const left = va === null ? 'n/a' : m.fmt(va)
                      const right = !b ? '' : ` / ${vb === null ? 'n/a' : m.fmt(vb)}`
                      return (
                        <PercentileRow
                          key={m.label}
                          label={m.label}
                          valueText={`${left}${right}`}
                          pctA={percentile(a, m.path)}
                          pctB={b ? percentile(b, m.path) : null}
                          hasB={Boolean(b)}
                        />
                      )
                    })}
                  </div>

                  <div className="mt-6 flex flex-wrap gap-6">
                    <span className="label text-ink flex items-center gap-2">
                      <span className="w-4 h-2.5 inline-block" style={{ backgroundColor: SERIES.a.stroke }} />
                      {a.name}
                    </span>
                    {b && (
                      <span className="label text-ink flex items-center gap-2">
                        <span className="w-4 h-2.5 inline-block" style={{ backgroundColor: SERIES.b.stroke }} />
                        {b.name}
                      </span>
                    )}
                  </div>
                  <p className="mt-4 max-w-read text-sm text-ink-soft">
                    The number beside each bar is the rank. A dash means the
                    position has fewer than five players to rank against, so no
                    rank was computed — which is not the same as ranking last,
                    and the two are drawn differently.
                  </p>
                </div>

                <div className="col-span-6 lg:col-span-2">
                  <h3 className="font-display text-2xl m-0 pb-3 border-b border-rule">Shape</h3>
                  <div className="mt-5">
                    <ResponsiveContainer width="100%" height={300}>
                      <RadarChart data={radarData} outerRadius="72%">
                        <PolarGrid stroke="#D8D7CC" />
                        <PolarAngleAxis dataKey="metric" tick={axisFont} />
                        <PolarRadiusAxis domain={[0, 100]} tickCount={3} tick={{ ...axisFont, fontSize: 9 }} />
                        {/* Solid against dashed, so the two silhouettes are
                            told apart by line style and not by colour alone. */}
                        <Radar name={a.name} dataKey="A" stroke={SERIES.a.stroke}
                          fill={SERIES.a.stroke} fillOpacity={0.16} strokeWidth={2.5} />
                        {b && <Radar name={b.name} dataKey="B" stroke={SERIES.b.stroke}
                          fill={SERIES.b.stroke} fillOpacity={0.12} strokeDasharray="5 3" strokeWidth={2} />}
                        <Tooltip />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="mt-2 max-w-read text-sm text-ink-soft">
                    One vertex per metric. The solid outline is A and the dashed
                    one is B: they read apart in greyscale, which is how a
                    printed report arrives at a meeting. A metric with no rank
                    sits at the centre here, so read the bars for those.
                  </p>
                </div>
              </div>

              {trendData.length > 0 && (
                <div className="section">
                  <h3 className="font-display text-2xl m-0 pb-3 border-b border-rule">
                    Match by match
                  </h3>
                  <div className="mt-5">
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart data={trendData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="2 4" stroke="#D8D7CC" vertical={false} />
                        <XAxis dataKey="label" tick={axisFont} stroke="#B6B4A6" />
                        {/* Rounded bounds and a formatted tick. The domain used
                            to be computed as dataMin - 5, which handed the axis
                            raw floats and printed 99.99999999999999 down the
                            side of the chart. Shared with PerformanceChart,
                            which kept the broken version of this for as long
                            as the formula lived in two files. */}
                        <YAxis
                          tick={axisFont}
                          stroke="#B6B4A6"
                          width={44}
                          domain={paddedDomain(5)}
                          tickFormatter={wholeTick}
                          allowDecimals={false}
                        />
                        <Tooltip formatter={(v: any) => (typeof v === 'number' ? v.toFixed(1) : v)} />
                        <Legend wrapperStyle={{ fontFamily: 'Archivo Narrow, Archivo, sans-serif', fontSize: 11 }} />
                        <Line type="monotone" dataKey="A" name={a.name} stroke={SERIES.a.stroke}
                          strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                        {b && <Line type="monotone" dataKey="B" name={b.name} stroke={SERIES.b.stroke}
                          strokeDasharray="5 3" strokeWidth={2} dot={{ r: 3 }} connectNulls />}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="mt-2 max-w-read text-sm text-ink-soft">
                    A rating per appearance, in order. A gap is a match without
                    a rating, not a zero.
                  </p>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}

export default Analytics
