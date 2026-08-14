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

  const statCards = [
    {
      title: 'Total Players',
      value: stats.totalPlayers.toString(),
      icon: Users,
      color: 'blue'
    },
    {
      title: 'Listed Clubs',
      value: stats.totalTeams.toString(),
      icon: Target,
      color: 'green'
    },
    {
      title: 'Avg Performance Index',
      value: stats.avgIndex.toFixed(1),
      icon: Activity,
      color: 'purple'
    },
    {
      title: 'Market Value',
      value: `€${(stats.totalMarketValue / 1_000_000_000).toFixed(2)}B`,
      icon: DollarSign,
      color: 'yellow'
    }
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-2">Welcome to Kümü Platform</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => {
          const Icon = stat.icon
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <div className={`p-3 rounded-lg bg-${stat.color}-100`}>
                  <Icon className={`w-6 h-6 text-${stat.color}-600`} />
                </div>

              </div>
              <h3 className="text-2xl font-bold text-gray-900">{stat.value}</h3>
              <p className="text-gray-600 text-sm mt-1">{stat.title}</p>
            </div>
          )
        })}
      </div>

      {/* Recent Activity Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Matches */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Highest Valued Players</h2>
          <div className="space-y-4">
            {stats.topValued.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <Users className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium">{p.name}</p>
                    <p className="text-sm text-gray-600">
                      {p.position} • {p.currentTeam} • €{((p.marketValue || 0) / 1_000_000).toFixed(1)}M
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {stats.topValued.length === 0 && (
              <p className="text-sm text-gray-500">Loading players...</p>
            )}
          </div>
        </div>

        {/* Top Performers */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Top Performers</h2>
          <div className="space-y-3">
            {stats.topPerformers.map((p: any) => (
              <div key={p.id} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gray-200 rounded-full"></div>
                  <div>
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-gray-600">
                      {p.position} • Index: {p.performanceIndex.value.toFixed(1)}
                    </p>
                  </div>
                </div>
                <Award className="w-4 h-4 text-yellow-500" />
              </div>
            ))}
            {stats.topPerformers.length === 0 && (
              <p className="text-sm text-gray-500">Loading...</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
