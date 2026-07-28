'use client'
import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface PerformanceChartProps {
  player: any
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ player }) => {
  const index = player?.performanceIndex || player?.performance_index || null
  const trend = index?.trend ?? 0

  // Real per-match history produced by the pipeline (not simulated).
  const history: any[] =
    player?.performanceHistory || player?.performance_history || []

  const data = history.map((h, i) => ({
    label: `M${i + 1}`,
    value: Number(((h?.rating ?? 0) * 10).toFixed(1)),
    goals: h?.goals ?? 0,
    assists: h?.assists ?? 0,
  }))

  if (data.length === 0) {
    return (
      <div className="mt-4 bg-gray-50 p-4 rounded-lg">
        <span className="text-sm font-medium text-gray-600">Match-by-match performance</span>
        <p className="text-sm text-gray-500 mt-2">No match data available for this player.</p>
      </div>
    )
  }

  const renderTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    const d = payload[0].payload
    return (
      <div className="bg-white border border-gray-200 rounded-md px-3 py-2 shadow-sm text-xs">
        <p className="font-medium text-gray-800">Match {label.replace('M', '')}</p>
        <p className="text-blue-600">Rating: {d.value.toFixed(1)}</p>
        {(d.goals > 0 || d.assists > 0) && (
          <p className="text-gray-600">
            {d.goals} goal{d.goals === 1 ? '' : 's'} • {d.assists} assist{d.assists === 1 ? '' : 's'}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="mt-4 bg-gray-50 p-4 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-600">
          Match-by-match performance ({data.length} matches)
        </span>
        <span
          className={`text-sm font-medium ${
            trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-600'
          }`}
        >
          {trend > 0 ? '+' : ''}
          {Number(trend).toFixed(2)} trend
        </span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} domain={['dataMin - 5', 'dataMax + 5']} />
          <Tooltip content={renderTooltip} />
          <Line type="monotone" dataKey="value" stroke="#3B82F6" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default PerformanceChart
