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
    activeMatches: 0,
    avgMatchScore: 0,
    recentActivity: []
  })

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      // Fetch actual data from API
      const players = await api.players.getAll({ limit: 100 })
      setStats(prev => ({
        ...prev,
        totalPlayers: players.length
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
      change: '+12%',
      icon: Users,
      color: 'blue'
    },
    {
      title: 'Active Matches',
      value: stats.activeMatches.toString(),
      change: '+8%',
      icon: Target,
      color: 'green'
    },
    {
      title: 'Avg Match Score',
      value: `${stats.avgMatchScore}%`,
      change: '+5%',
      icon: Activity,
      color: 'purple'
    },
    {
      title: 'Market Value',
      value: '€250M',
      change: '+15%',
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
                <span className="text-green-600 text-sm font-medium">{stat.change}</span>
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
          <h2 className="text-xl font-semibold mb-4">Recent Matches</h2>
          <div className="space-y-4">
            {[1, 2, 3].map((item) => (
              <div key={item} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <Users className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-medium">Player {item} matched with Team {item}</p>
                    <p className="text-sm text-gray-600">Match Score: {85 + item}%</p>
                  </div>
                </div>
                <button 
                  onClick={handleViewReport}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  View Report
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Top Performers */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Top Performers</h2>
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((item) => (
              <div key={item} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gray-200 rounded-full"></div>
                  <div>
                    <p className="text-sm font-medium">Player {item}</p>
                    <p className="text-xs text-gray-600">Performance: {90 - item * 2}%</p>
                  </div>
                </div>
                <Award className="w-4 h-4 text-yellow-500" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
