'use client'
import { Home, Search, FileText, BarChart3, Users, TrendingUp, Shield, Upload } from 'lucide-react'

interface NavigationProps {
  activeView: string
  setActiveView: (view: string) => void
}

/**
 * The bar in the Cancha language.
 *
 * Ink ground rather than white: the page below is chalk, and a white bar on a
 * chalk page is a seam nobody asked for. On ink the bar reads as the frame of
 * the instrument and the content reads as the paper inside it.
 *
 * The active tab is marked by a clay rule under the label, not by a filled
 * pill. A pill is a button that has already been pressed; a rule is a place
 * marker, which is what a tab is. It also leaves clay free to keep meaning
 * "series A" everywhere else without the nav shouting over it.
 */
export default function Navigation({ activeView, setActiveView }: NavigationProps) {
  const navItems = [
    { id: 'dashboard', name: 'Dashboard', icon: Home },
    { id: 'matching', name: 'Player Matching', icon: Search },
    { id: 'report', name: 'Scouting Report', icon: FileText },
    { id: 'analytics', name: 'Analytics', icon: BarChart3 },
    { id: 'market', name: 'Market', icon: TrendingUp },
    { id: 'squads', name: 'Squads', icon: Shield },
    { id: 'upload', name: 'Your Data', icon: Upload },
  ]

  return (
    <nav className="bg-ink sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center min-h-[68px] gap-6">
          <button
            onClick={() => setActiveView('dashboard')}
            className="flex items-center gap-3 shrink-0 cursor-pointer bg-transparent border-0 p-0
                       hover:opacity-80 transition-opacity"
          >
            <span className="w-8 h-8 bg-clay flex items-center justify-center shrink-0">
              <Users className="w-5 h-5 text-paper" aria-hidden="true" />
            </span>
            <span className="font-display text-2xl font-bold tracking-tight text-paper">Kümü</span>
          </button>

          <div className="hidden md:flex items-stretch gap-5 lg:gap-7 overflow-x-auto">
            {navItems.map((item) => {
              const Icon = item.icon
              const active = activeView === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveView(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`font-label text-label font-semibold uppercase whitespace-nowrap
                              border-b-2 transition-colors bg-transparent ${
                    active
                      ? 'text-paper border-clay'
                      : 'text-grass-shade border-transparent hover:text-paper'
                  }`}
                  style={{ minHeight: 44 }}
                >
                  <span className="flex items-center gap-2">
                    <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
                    {item.name}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
      {/* The tagline used to sit here and competed with the tabs for width.
          At seven tabs it lost: the two overlapped into an unreadable pile.
          It already appears on the dashboard, so the bar keeps the space. */}
    </nav>
  )
}
