'use client'

import React from 'react'
import { User, Activity, DollarSign, Flag } from 'lucide-react'
import { Player } from '@/types'

interface PlayerCardProps {
  player: Player
  onClick: () => void
  isSelected?: boolean
}

const PlayerCard: React.FC<PlayerCardProps> = ({ player, onClick, isSelected }) => {
  // Safely access nested properties with fallbacks
  const performanceValue = player?.performanceIndex?.value || 0
  const trend = player?.performanceIndex?.trend || 0
  const marketValue = player?.marketValue || 0
  
  return (
    <div 
      className={`bg-white rounded-lg shadow-md p-6 cursor-pointer transition-all hover:shadow-lg ${
        isSelected ? 'ring-2 ring-blue-500' : ''
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center">
            <User className="w-6 h-6 text-gray-600" />
          </div>
          <div>
            <h3 className="font-semibold text-lg">{player.name}</h3>
            <p className="text-sm text-gray-500">{player.position} • {player.age} years</p>
          </div>
        </div>
      </div>
      
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Activity className="w-3 h-3 text-gray-400" />
          <span className="text-gray-600">
            Index: {performanceValue.toFixed(1)}
          </span>
        </div>
        <div className={`flex items-center gap-1 ${
          trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-600'
        }`}>
          <span className="text-sm">
            Trend: {trend > 0 ? '+' : ''}{trend.toFixed(1)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Flag className="w-3 h-3 text-gray-400" />
          <span className="text-sm text-gray-600">{player.nationality}</span>
        </div>
        <div className="flex items-center gap-2">
          <DollarSign className="w-3 h-3 text-gray-400" />
          <span className="text-sm text-gray-600">
            €{(marketValue / 1000000).toFixed(1)}M
          </span>
        </div>
      </div>
    </div>
  )
}

export default PlayerCard
