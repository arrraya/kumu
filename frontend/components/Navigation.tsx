'use client'
import { Home, Search, FileText, BarChart3, Users, TrendingUp, Shield, Upload } from 'lucide-react'

interface NavigationProps {
  activeView: string
  setActiveView: (view: string) => void
}

export default function Navigation({ activeView, setActiveView }: NavigationProps) {
  const navItems = [
    { id: 'dashboard', name: 'Dashboard', icon: Home },
    { id: 'matching', name: 'Player Matching', icon: Search },
    { id: 'report', name: 'Scouting Report', icon: FileText },
    { id: 'analytics', name: 'Analytics', icon: BarChart3 },
    { id: 'market', name: 'Market', icon: TrendingUp },
    { id: 'squads', name: 'Squads', icon: Shield },
    { id: 'upload', name: 'Your Data', icon: Upload }
  ]

  return (
    <nav className="bg-white shadow-sm border-b sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-16 gap-4">
          <div className="flex items-center gap-6 min-w-0 flex-1">
            <button onClick={() => setActiveView('dashboard')} className="flex items-center gap-3 shrink-0 cursor-pointer hover:opacity-80 transition-opacity bg-transparent border-0 p-0">
              <div className="w-10 h-10 bg-green-600 rounded-lg flex items-center justify-center">
                <Users className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">Kümü</h1>
            </button>
            
            <div className="hidden md:flex items-center gap-1 lg:gap-3 overflow-x-auto">
              {navItems.map((item) => {
                const Icon = item.icon
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveView(item.id)}
                    className={`px-2 lg:px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${
                      activeView === item.id
                        ? 'bg-green-50 text-green-700'
                        : 'text-gray-700 hover:text-gray-900'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4" />
                      {item.name}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
          {/* The tagline used to sit here and competed with the tabs for width.
              At seven tabs it lost: the two overlapped into an unreadable pile.
              It already appears on the dashboard, so the bar keeps the space. */}
        </div>
      </div>
    </nav>
  )
}
