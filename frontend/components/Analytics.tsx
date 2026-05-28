'use client'

import React from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const Analytics = ({ players = [] }) => {
  // Sample data for when metrics are missing
  const defaultMetrics = {
    passing: { completion: 0.85, accuracy: 0.82 },
    shooting: { accuracy: 0.45, shotsPerGame: 3.2 },
    defending: { tackles: 2.5, interceptions: 1.8 },
    pace: { speed: 85, acceleration: 88 }
  }

  // Safely get metric value with fallback
  const getMetricValue = (player: any, path: string, defaultValue: number = 0) => {
    try {
      const keys = path.split('.')
      let value = player
      for (const key of keys) {
        value = value?.[key]
        if (value === undefined) return defaultValue
      }
      return value
    } catch {
      return defaultValue
    }
  }

  // Get first player or use default
  const player = players[0] || {
    name: 'Select a player',
    metrics: defaultMetrics,
    performance_index: { value: 75 }
  }

  // Performance data for chart
  const performanceData = [
    { name: 'Jan', value: 72 },
    { name: 'Feb', value: 74 },
    { name: 'Mar', value: 71 },
    { name: 'Apr', value: 78 },
    { name: 'May', value: 82 },
    { name: 'Jun', value: 85 }
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h2 className="text-2xl font-bold mb-6">Player Analytics Dashboard</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Performance Index Card */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold mb-4">Performance Index</h3>
          <div className="text-4xl font-bold text-blue-600">
            {getMetricValue(player, 'performance_index.value', 75).toFixed(1)}
          </div>
          <p className="text-gray-600 mt-2">Current Rating</p>
        </div>

        {/* Key Stats Grid */}
        <div className="bg-white rounded-lg shadow-md p-6 col-span-2">
          <h3 className="text-lg font-semibold mb-4">Key Statistics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-green-50 p-4 rounded-lg">
              <div className="text-sm text-green-600 font-medium">Pass Completion</div>
              <div className="text-2xl font-bold text-green-900">
                {(() => {
                  const completion = getMetricValue(player, 'metrics.passing.completion', 0.85)
                  return completion > 1 ? `${completion.toFixed(1)}%` : `${(completion * 100).toFixed(1)}%`
                })()}
              </div>
            </div>
            <div className="bg-blue-50 p-4 rounded-lg">
              <div className="text-sm text-blue-600 font-medium">Shot Accuracy</div>
              <div className="text-2xl font-bold text-blue-900">
                {(() => {
                  const accuracy = getMetricValue(player, 'metrics.shooting.accuracy', 0.45)
                  return accuracy > 1 ? `${accuracy.toFixed(1)}%` : `${(accuracy * 100).toFixed(1)}%`
                })()}
              </div>
            </div>
            <div className="bg-yellow-50 p-4 rounded-lg">
              <div className="text-sm text-yellow-600 font-medium">Tackles/Game</div>
              <div className="text-2xl font-bold text-yellow-900">
                {getMetricValue(player, 'metrics.defending.tackles', 2.5).toFixed(1)}
              </div>
            </div>
            <div className="bg-purple-50 p-4 rounded-lg">
              <div className="text-sm text-purple-600 font-medium">Pace</div>
              <div className="text-2xl font-bold text-purple-900">
                {getMetricValue(player, 'metrics.pace.speed', 85).toFixed(0)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h3 className="text-lg font-semibold mb-4">Performance Trend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default Analytics
