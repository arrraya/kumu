'use client'
import React, { useMemo, useState } from 'react'

/**
 * A player's spatial fingerprint, drawn from the stored zone matrix.
 *
 * Kumü had no spatial representation at all: a scouting report described where
 * a player operates in words and numbers. A heat map says it in a second, and
 * it is the same data the style derivation uses, so nothing extra is fetched.
 *
 * Both views come from one matrix. Touch zones are the occupancy marginal;
 * flows are the strongest zone-to-zone pass links. Below the reliability
 * threshold the map still draws but says the sample is thin, rather than
 * presenting a shape built on forty passes as if it were a pattern.
 */

type Profile = {
  grid?: { cols: number; rows: number; pitch: [number, number] }
  pass_flows?: Record<string, number>
  touch_zones?: Record<string, number>
  passes_counted?: number
  reliable?: boolean
}

const W = 120
const H = 80

const PitchMap: React.FC<{ profile?: Profile | null; name?: string }> = ({ profile, name }) => {
  const [view, setView] = useState<'touches' | 'flows'>('touches')

  const grid = profile?.grid ?? { cols: 6, rows: 4, pitch: [W, H] as [number, number] }
  const cw = W / grid.cols
  const ch = H / grid.rows

  const zoneBox = (z: number) => ({
    x: (z % grid.cols) * cw,
    y: Math.floor(z / grid.cols) * ch,
  })
  const zoneCentre = (z: number) => ({
    cx: ((z % grid.cols) + 0.5) * cw,
    cy: (Math.floor(z / grid.cols) + 0.5) * ch,
  })

  const touches = useMemo(() => {
    const t = profile?.touch_zones ?? {}
    const max = Math.max(1, ...Object.values(t))
    return Object.entries(t).map(([z, n]) => ({ z: Number(z), n, w: n / max }))
  }, [profile])

  const flows = useMemo(() => {
    const f = profile?.pass_flows ?? {}
    const all = Object.entries(f).map(([k, n]) => {
      const [from, to] = k.split('-').map(Number)
      return { from, to, n }
    })
    // Only the strongest links: drawing all 576 possible pairs is a smear, and
    // the shape of a player's game lives in the handful he repeats.
    return all.sort((a, b) => b.n - a.n).slice(0, 16)
  }, [profile])

  const maxFlow = Math.max(1, ...flows.map((f) => f.n))
  const hasData = touches.length > 0 || flows.length > 0

  if (!profile || !hasData) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="font-medium text-gray-900">Where he plays</h3>
        <p className="text-sm text-gray-600 mt-2">
          No spatial data for this player. Positional data requires event
          coordinates, which not every feed carries.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-medium text-gray-900">Where he plays</h3>
        <div className="flex gap-1 text-xs">
          {(['touches', 'flows'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-2 py-1 rounded ${
                view === v ? 'bg-green-50 text-green-700 font-medium' : 'text-gray-600'
              }`}
            >
              {v === 'touches' ? 'Involvement' : 'Passing'}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-3">
        {profile.passes_counted ?? 0} completed passes
        {profile.reliable === false && ' · thin sample, read the shape loosely'}
        {name ? ` · ${name}` : ''} · attacking left to right
      </p>

      {/* Capped width: the pitch is 3:2, so a full-width svg on a desktop
          column grew past the viewport and pushed the heading and the
          view toggle off the top of the screen — the control for the map
          was scrolled away by the map itself. */}
      <div className="mx-auto w-full max-w-[560px]">
      <svg viewBox={`-2 -2 ${W + 4} ${H + 4}`} className="w-full">
        <rect x="0" y="0" width={W} height={H} fill="#f7faf8" stroke="#cbd5d0" strokeWidth="0.4" />
        <line x1={W / 2} y1="0" x2={W / 2} y2={H} stroke="#cbd5d0" strokeWidth="0.4" />
        <circle cx={W / 2} cy={H / 2} r="9.15" fill="none" stroke="#cbd5d0" strokeWidth="0.4" />
        <rect x="0" y={(H - 40) / 2} width="16.5" height="40" fill="none" stroke="#cbd5d0" strokeWidth="0.4" />
        <rect x={W - 16.5} y={(H - 40) / 2} width="16.5" height="40" fill="none" stroke="#cbd5d0" strokeWidth="0.4" />

        {view === 'touches' &&
          touches.map(({ z, w }) => {
            const { x, y } = zoneBox(z)
            return (
              <rect key={z} x={x} y={y} width={cw} height={ch}
                fill="#16a34a" opacity={0.08 + w * 0.62} />
            )
          })}

        {view === 'flows' && (
          <>
            <defs>
              {/* userSpaceOnUse: by default an arrowhead scales with stroke
                  width, so the strongest flows grew heads that swallowed the
                  pitch. Fixed size keeps the line weight carrying the volume. */}
              <marker id="kumu-arrow" viewBox="0 0 10 10" refX="8" refY="5"
                markerWidth="3" markerHeight="3" markerUnits="userSpaceOnUse"
                orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#16a34a" />
              </marker>
            </defs>
            {flows.map(({ from, to, n }, i) => {
              const a = zoneCentre(from)
              const b = zoneCentre(to)
              if (from === to) {
                return <circle key={i} cx={a.cx} cy={a.cy} r={1 + (n / maxFlow) * 2.5}
                  fill="#16a34a" opacity="0.45" />
              }
              return (
                <line key={i} x1={a.cx} y1={a.cy} x2={b.cx} y2={b.cy}
                  stroke="#16a34a" strokeWidth={0.25 + (n / maxFlow) * 1.1}
                  opacity={0.25 + (n / maxFlow) * 0.5}
                  markerEnd="url(#kumu-arrow)" />
              )
            })}
          </>
        )}

        {Array.from({ length: grid.cols - 1 }, (_, i) => (
          <line key={`v${i}`} x1={(i + 1) * cw} y1="0" x2={(i + 1) * cw} y2={H}
            stroke="#e2e8e5" strokeWidth="0.2" />
        ))}
        {Array.from({ length: grid.rows - 1 }, (_, i) => (
          <line key={`h${i}`} x1="0" y1={(i + 1) * ch} x2={W} y2={(i + 1) * ch}
            stroke="#e2e8e5" strokeWidth="0.2" />
        ))}
      </svg>
      </div>
    </div>
  )
}

export default PitchMap
