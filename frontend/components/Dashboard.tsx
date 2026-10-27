'use client'

import React, { useState, useEffect } from 'react'
import { TrendingUp, Users, DollarSign, Activity, Target, Clock, Globe, Award } from 'lucide-react'
import { api } from '@/lib/api'

interface DashboardProps {
  setActiveView?: (view: string) => void
}

const Dashboard: React.FC<DashboardProps> = ({ setActiveView }) => {
  const [stats, setStats] = useState({
    totalPlayers: 0,
    totalTeams: 0,
    avgIndex: 0,
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
      const avgIndex = withIndex.length
        ? withIndex.reduce((s: number, p: any) => s + p.performanceIndex.value, 0) / withIndex.length
        : 0

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
        avgIndex,
        totalMarketValue,
        topPerformers,
        topValued,
      }))
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    }
  }

  // Handle view report - either use passed function or handle locally
  const handleViewReport = () => {
    if (setActiveView) {
      setActiveView('report')
    } else {
      console.log('Viewing report - no handler provided')
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
    { title: 'Median index', value: stats.avgIndex.toFixed(1) },
    {
      title: 'Combined value',
      value: `€${(stats.totalMarketValue / 1_000_000_000).toFixed(2)}B`,
      // Every value in that sum is Kumü's own estimate, not an observed fee.
      estimated: true,
    },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="font-display text-4xl text-ink leading-tight">
          Reference population
        </h1>
        <p className="mt-2 max-w-read text-ink-soft">
          What every index and percentile in Kümü is measured against.
          Combined value is <span className="is-estimated">estimated</span>;
          no observed transfer fee enters it.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => (
          <div key={index} className="border-t-2 border-rule pt-3">
            <div className={`figure ${stat.estimated ? 'is-estimated' : ''}`}>
              {stat.value}
            </div>
            <p className="text-sm text-ink-faint mt-1">{stat.title}</p>
          </div>
        ))}
      </div>

      {/* Recent Activity Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Matches */}
        <div className="lg:col-span-2 bg-white border border-rule rounded-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Highest Valued Players</h2>
          <div className="space-y-4">
            {stats.topValued.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-sm">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <Users className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium">{p.name}</p>
                    <p className="text-sm text-ink-soft">
                      {p.position} • {p.currentTeam} • {typeof p.marketValue === 'number' ? `€${(p.marketValue / 1_000_000).toFixed(1)}M` : 'value n/a'}
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {stats.topValued.length === 0 && (
              <p className="text-sm text-ink-faint">Loading players...</p>
            )}
          </div>
        </div>

        {/* Top Performers */}
        <div className="bg-white border border-rule rounded-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Top Performers</h2>
          <div className="space-y-3">
            {stats.topPerformers.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gray-200 rounded-full"></div>
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-ink-soft">
                      {p.position} • Index: {p.performanceIndex.value.toFixed(1)}
                    </p>
                  </div>
                </div>
                <Award className="w-4 h-4 text-yellow-500" />
              </div>
            ))}
            {stats.topPerformers.length === 0 && (
              <p className="text-sm text-ink-faint">Loading...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
