'use client'

import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface PerformanceChartProps {
  player: any
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ player }) => {
  // Safely access performance index with fallback
  const performanceValue = player?.performanceIndex?.value || player?.performance_index?.value || 75
  const trend = player?.performanceIndex?.trend || player?.performance_index?.trend || 0
  
  // Generate sample performance data
  const generatePerformanceData = () => {
    const data = []
    for (let i = 5; i >= 0; i--) {
      data.push({
        month: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'][5 - i],
        value: performanceValue - (i * 2) + Math.random() * 5
      })
    }
    return data
  }

  const data = generatePerformanceData()

  return (
    <div className="mt-4 bg-gray-50 p-4 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-600">Recent Performance</span>
        <span className={`text-sm font-medium ${trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-600'}`}>
          {trend > 0 ? '+' : ''}{trend.toFixed(1)}% trend
        </span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="month" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} domain={[60, 100]} />
          <Tooltip />
          <Line 
            type="monotone" 
            dataKey="value" 
            stroke="#3B82F6" 
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default PerformanceChart
