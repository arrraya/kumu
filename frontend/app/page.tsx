'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import type { Player, Match } from '@/types'

const Navigation = dynamic(() => import('@/components/Navigation'), { ssr: false })
const Dashboard = dynamic(() => import('@/components/Dashboard'), { ssr: false })
const PlayerMatching = dynamic(() => import('@/components/PlayerMatching'), { ssr: false })
const ScoutingReport = dynamic(() => import('@/components/ScoutingReport'), { ssr: false })
const Analytics = dynamic(() => import('@/components/Analytics'), { ssr: false })

export default function Home() {
  const [activeView, setActiveView] = useState('dashboard')
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null)
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null)

  return (
    <div className="min-h-screen bg-green-50">
      <Navigation activeView={activeView} setActiveView={setActiveView} />
      
      {activeView === 'dashboard' && (
        <Dashboard 
          setActiveView={setActiveView}
          selectedPlayer={selectedPlayer}
          selectedMatch={selectedMatch}
        />
      )}
      
      {activeView === 'matching' && (
        <PlayerMatching
          selectedPlayer={selectedPlayer}
          setSelectedPlayer={(player: Player | null) => setSelectedPlayer(player)}
          selectedMatch={selectedMatch}
          setSelectedMatch={(match: Match | null) => setSelectedMatch(match)}
          setActiveView={setActiveView}
        />
      )}
      
      {activeView === 'report' && (
        <ScoutingReport
          player={selectedPlayer}
          match={selectedMatch}
        />
      )}
      
      {activeView === 'analytics' && (
        <Analytics player={selectedPlayer} />
      )}
    </div>
  )
}
