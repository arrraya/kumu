'use client'

import React, { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { valueMark, valueTitle, money } from '@/lib/provenance'

interface DashboardProps {
  setActiveView?: (view: string) => void
}

/**
 * A quantile by linear interpolation between order statistics — the same
 * definition numpy and R use by default, so a figure here matches one computed
 * in the pipeline rather than differing by a rounding convention.
 *
 * The dashboard reported a MEAN under the label "median". The two are not
 * interchangeable in a population with Messi in it, and the median is the
 * right statistic here for a reason beyond robustness: everything else in
 * Kumü is rank-based. A percentile of 50 is defined as the typical player for
 * the position, and the median index is exactly the index of the player at
 * that rank. The mean corresponds to nothing else on any screen.
 *
 * Expects xs already sorted ascending.
 */
const quantile = (xs: number[], q: number): number => {
  if (xs.length === 0) return 0
  const pos = (xs.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return lo === hi ? xs[lo] : xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)
}

const Dashboard: React.FC<DashboardProps> = ({ setActiveView }) => {
  const [stats, setStats] = useState({
    totalPlayers: 0,
    totalTeams: 0,
    medianIndex: 0,
    q1Index: 0,
    q3Index: 0,
    indexedPlayers: 0,
    totalMarketValue: 0,
    topPerformers: [] as any[],
    topValued: [] as any[],
    activeMatches: 0,
    avgMatchScore: 0,
    recentActivity: []
  })

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      // Fetch actual data from API (pipeline-produced players)
      const players = await api.players.getAll({ limit: 500 })
      const withIndex = players.filter((p: any) => p.performanceIndex?.value)
      const topPerformers = [...withIndex]
        .sort((a: any, b: any) => b.performanceIndex.value - a.performanceIndex.value)
        .slice(0, 5)
      const topValued = [...players]
        .sort((a: any, b: any) => (b.marketValue || 0) - (a.marketValue || 0))
        .slice(0, 3)
      const totalMarketValue = players.reduce((s: number, p: any) => s + (p.marketValue || 0), 0)
      // Only players who actually have an index. A player without one is not
      // a zero; he is absent from this distribution, and counting him as a
      // zero would drag every summary figure down.
      const indexes = withIndex
        .map((p: any) => p.performanceIndex.value as number)
        .sort((a: number, b: number) => a - b)
      const medianIndex = quantile(indexes, 0.5)
      const q1Index = quantile(indexes, 0.25)
      const q3Index = quantile(indexes, 0.75)

      // Teams are a separate call; failing here should not blank the dashboard.
      let totalTeams = 0
      try {
        // Only clubs: national sides live in the same table but are squads,
        // not entities a user operates on from this dashboard.
        const teams = await api.teams.getAll({ limit: 100 })
        totalTeams = (teams || []).filter((t: any) => t.teamType !== 'national').length
      } catch (e) {
        console.error('Teams fetch failed:', e)
      }

      setStats(prev => ({
        ...prev,
        totalPlayers: players.length,
        totalTeams,
        medianIndex,
        q1Index,
        q3Index,
        indexedPlayers: indexes.length,
        totalMarketValue,
        topPerformers,
        topValued,
      }))
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    }
  }

  // Four readings of the same reference population, so they share one
  // treatment. The icons they used to carry were tinted through a class name
  // built at runtime — Tailwind only emits classes it can see written out, so
  // those tints never existed, and four colours would have encoded nothing
  // anyway.
  const statCards = [
    { title: 'Players', value: stats.totalPlayers.toString() },
    { title: 'Clubs', value: stats.totalTeams.toString() },
    {
      title: 'Median index',
      value: stats.medianIndex.toFixed(1),
      // A centre with no spread hides the distribution it claims to summarise.
      // The middle half of the population sits between these two.
      note: stats.indexedPlayers
        ? `middle half ${stats.q1Index.toFixed(1)}–${stats.q3Index.toFixed(1)} · ${stats.indexedPlayers} indexed`
        : undefined,
    },
    {
      title: 'Combined value',
      value: `€${(stats.totalMarketValue / 1_000_000_000).toFixed(2)}B`,
      // Every value in that sum is Kumü's own estimate, not an observed fee.
      estimated: true,
    },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="masthead">
        <div className="label text-clay-ink mb-3">Dashboard · the reference population</div>
        <h1 className="font-display text-4xl md:text-5xl leading-none m-0">
          Reference population
        </h1>
        <p className="mt-4 max-w-read text-lg text-ink-soft">
          What every index and percentile in Kümü is measured against.
          Combined value is <span className="is-estimated">estimated</span>;
          no observed transfer fee enters it.
        </p>
      </div>

      {/* The four figures. A rule above each, no box around it: in this
          language rules separate and boxes enclose, and these four are one
          reading split four ways, not four cards. */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mt-10">
        {statCards.map((stat, index) => (
          <div key={index} className="border-t-2 border-ink pt-3">
            <div className={`figure ${stat.estimated ? 'is-estimated' : ''}`}>
              {stat.value}
            </div>
            <p className="label mt-2">{stat.title}</p>
            {stat.note && (
              <p className="mt-1 text-xs text-ink-faint tabular">{stat.note}</p>
            )}
          </div>
        ))}
      </div>

      <div className="section grid grid-cols-1 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-10">
        <div>
          <h2 className="font-display text-2xl m-0 pb-3 border-b border-rule">
            Highest valued players
          </h2>
          <div className="mt-2">
            {stats.topValued.map((p: any, i: number) => (
              <div key={p.id}
                className="flex items-center justify-between gap-4 py-4 border-b border-rule last:border-0">
                <div className="flex items-baseline gap-4 min-w-0">
                  {/* A rank numeral instead of an avatar. Kumü has no photos,
                      and a grey circle standing in for one is furniture. */}
                  <span className="font-label text-label font-semibold text-ink-faint tabular shrink-0">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium truncate m-0">{p.name}</p>
                    <p className="label mt-1">{p.position} • {p.currentTeam}</p>
                  </div>
                </div>
                <span className={`tabular text-lg shrink-0 ${valueMark(p)}`} title={valueTitle(p)}>
                  {money(p.marketValue)}
                </span>
              </div>
            ))}
            {stats.topValued.length === 0 && (
              <p className="text-sm text-ink-faint py-4">Loading players…</p>
            )}
          </div>
          {setActiveView && (
            <button type="button" onClick={() => setActiveView('market')}
              className="label mt-5 text-clay-ink hover:text-ink">
              See the market tab →
            </button>
          )}
        </div>

        <div>
          <h2 className="font-display text-2xl m-0 pb-3 border-b border-rule">
            Top performers
          </h2>
          <div className="mt-2">
            {stats.topPerformers.map((p: any, i: number) => (
              <div key={p.id}
                className="flex items-center justify-between gap-4 py-3.5 border-b border-rule last:border-0">
                <div className="flex items-baseline gap-4 min-w-0">
                  <span className="font-label text-label font-semibold text-ink-faint tabular shrink-0">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate m-0">{p.name}</p>
                    <p className="label mt-1">{p.position}</p>
                  </div>
                </div>
                {/* The index is the ranking key, so it is the figure. The gold
                    medal icon that used to sit here ranked nothing. */}
                <span className="font-display text-xl font-bold tabular shrink-0">
                  {p.performanceIndex.value.toFixed(1)}
                </span>
              </div>
            ))}
            {stats.topPerformers.length === 0 && (
              <p className="text-sm text-ink-faint py-4">Loading…</p>
            )}
          </div>
          <p className="mt-4 max-w-read text-sm text-ink-soft">
            Ranked by index across every position. A striker and a centre back
            are not doing the same job, so compare within a position in
            Analytics before reading much into the order.
          </p>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
