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
 *
 * In the Cancha language this component is not an illustration inside a tab:
 * the six-by-four grid it draws IS the layout grammar of every spatial screen,
 * so the map is sized and framed as the primary figure, not as a thumbnail.
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

/**
 * How many zone-to-zone links to draw.
 *
 * Sixteen was chosen when this map was a 560px thumbnail inside the scouting
 * report. At figure size sixteen straight lines cross each other into a
 * scribble, and a fingerprint nobody can read is worse than a shorter one.
 */
const TOP_FLOWS = 12

// How far short of the destination's centre an arrow stops, in pitch units.
// A head that lands exactly on the centre sits on top of the zone's own mark
// and the eye cannot tell which zone the pass arrived in.
const STOP_SHORT = 3.2
const START_AFTER = 1.6

// Series colours, as the system defines them: clay is A, slate is B. They
// differ in hue AND lightness, so the map survives a greyscale printout —
// clubs print, and a figure that only works on screen is half a figure.
const TONES = {
  a: { ink: '#C25A3A', mark: '#A6462A' },
  b: { ink: '#3A5A7A', mark: '#2F4A66' },
} as const

const PitchMap: React.FC<{
  profile?: Profile | null
  name?: string
  tone?: keyof typeof TONES
}> = ({ profile, name, tone = 'a' }) => {
  const [view, setView] = useState<'touches' | 'flows'>('touches')
  const colour = TONES[tone]

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
    return all.sort((a, b) => b.n - a.n).slice(0, TOP_FLOWS)
  }, [profile])

  const maxFlow = Math.max(1, ...flows.map((f) => f.n))
  const hasData = touches.length > 0 || flows.length > 0

  if (!profile || !hasData) {
    return (
      <div className="panel">
        <h3 className="font-display text-xl">Where they play</h3>
        <p className="mt-2 max-w-read text-ink-soft">
          No spatial data for this player. Positional data requires event
          coordinates, which not every feed carries.
        </p>
      </div>
    )
  }

  return (
    // One column for the whole figure. The heading and the view toggle used to
    // span the full page while the pitch was capped and centred, which left the
    // control for the map a screen's width away from the map.
    <figure className="m-0 mx-auto w-full max-w-[860px]">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-3">
        <h3 className="font-display text-2xl m-0">Where they play</h3>
        <div className="flex" role="group" aria-label="Map view">
          {(['touches', 'flows'] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setView(v)}
              aria-pressed={view === v}
              className={`font-label text-label font-semibold uppercase px-4 py-2.5 border-2 border-ink -ml-0.5 first:ml-0 ${
                view === v ? 'bg-ink text-paper' : 'bg-transparent text-ink hover:bg-paper-sunk'
              }`}
              style={{ minHeight: 44 }}
            >
              {v === 'touches' ? 'Involvement' : 'Passing'}
            </button>
          ))}
        </div>
      </div>

      <svg
        viewBox={`-2 -2 ${W + 4} ${H + 4}`}
        className="w-full block pitch"
        role="img"
        aria-label={
          view === 'touches'
            ? `Zones where ${name ?? 'the player'} is involved, attacking left to right`
            : `Strongest zone-to-zone pass links for ${name ?? 'the player'}, attacking left to right`
        }
      >
        {/* Chalk markings on grass. The ground colour comes from the .pitch
            class on the svg itself so it matches every other pitch in the
            product without a second source of truth. */}
        <line x1={W / 2} y1="0" x2={W / 2} y2={H} stroke="#FBFAF5" strokeWidth="0.5" />
        <circle cx={W / 2} cy={H / 2} r="9.15" fill="none" stroke="#FBFAF5" strokeWidth="0.5" />
        <rect x="0" y={(H - 40) / 2} width="16.5" height="40" fill="none" stroke="#FBFAF5" strokeWidth="0.5" />
        <rect x={W - 16.5} y={(H - 40) / 2} width="16.5" height="40" fill="none" stroke="#FBFAF5" strokeWidth="0.5" />

        {/* The zone grid, drawn under the data: dashed so it reads as a
            measuring frame rather than as pitch markings. */}
        {Array.from({ length: grid.cols - 1 }, (_, i) => (
          <line key={`v${i}`} x1={(i + 1) * cw} y1="0" x2={(i + 1) * cw} y2={H}
            stroke="#8A9479" strokeWidth="0.2" strokeDasharray="1 1.6" />
        ))}
        {Array.from({ length: grid.rows - 1 }, (_, i) => (
          <line key={`h${i}`} x1="0" y1={(i + 1) * ch} x2={W} y2={(i + 1) * ch}
            stroke="#8A9479" strokeWidth="0.2" strokeDasharray="1 1.6" />
        ))}

        {view === 'touches' &&
          touches.map(({ z, w }) => {
            const { x, y } = zoneBox(z)
            // A linear ramp painted almost the whole pitch in one mid tone: a
            // midfielder touches the ball nearly everywhere, so the zones he
            // actually lives in were lost in the wash. The exponent pushes the
            // middle of the distribution down and leaves the peak standing.
            const weight = Math.pow(w, 1.8)
            return (
              <rect key={z} x={x} y={y} width={cw} height={ch}
                fill={colour.ink} opacity={0.04 + weight * 0.66} />
            )
          })}

        {view === 'flows' && (
          <>
            <defs>
              {/* userSpaceOnUse: by default an arrowhead scales with stroke
                  width, so the strongest flows grew heads that swallowed the
                  pitch. Fixed size keeps the line weight carrying the volume.

                  Two units, not three: at figure size a three-unit head is
                  2.5% of the pitch width and reads as the mark itself rather
                  than as the direction of one. */}
              <marker id={`kumu-arrow-${tone}`} viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="2" markerHeight="2" markerUnits="userSpaceOnUse"
                orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill={colour.ink} />
              </marker>
            </defs>
            {flows.map(({ from, to, n }, i) => {
              const a = zoneCentre(from)
              const b = zoneCentre(to)
              const share = n / maxFlow

              if (from === to) {
                // Circulation inside one zone. A filled disc read as a smudge
                // under the arrowheads; a ring reads as a loop, which is what
                // it is, and lets the shading below show through.
                //
                // The ring has to be visibly hollow or it is just a dot again:
                // a thick stroke on a small radius closes the hole, so the
                // radius carries the volume here and the stroke stays thin.
                return (
                  <circle key={i} cx={a.cx} cy={a.cy} r={2.4 + share * 3.0}
                    fill="none" stroke={colour.ink}
                    strokeWidth={0.3 + share * 0.35} opacity="0.85" />
                )
              }

              // Stop short of both ends so the head lands inside the arriving
              // zone instead of on its centre, and the tail leaves the
              // departing one instead of starting on top of it.
              const dx = b.cx - a.cx
              const dy = b.cy - a.cy
              const len = Math.hypot(dx, dy) || 1
              const ux = dx / len
              const uy = dy / len
              const trim = Math.min(STOP_SHORT, len * 0.3)
              const lead = Math.min(START_AFTER, len * 0.15)

              return (
                <line key={i}
                  x1={a.cx + ux * lead} y1={a.cy + uy * lead}
                  x2={b.cx - ux * trim} y2={b.cy - uy * trim}
                  stroke={colour.ink} strokeWidth={0.3 + share * 1.0}
                  // A narrow alpha band: wide opacity ranges made the weaker
                  // links vanish and the overlaps muddy. Volume is the line's
                  // weight, not its transparency.
                  opacity={0.55 + share * 0.4}
                  markerEnd={`url(#kumu-arrow-${tone})`} strokeLinecap="round" />
              )
            })}
          </>
        )}

        {/* Direction of play, stated on the figure itself. A caption under a
            pitch is read after the shape, which is too late. */}
        <text x="2" y={H - 2} fontFamily="Archivo Narrow, Archivo, sans-serif"
          fontSize="3.4" fontWeight="600" letterSpacing="0.3" fill="#1B1F1A">OWN GOAL</text>
        <text x={W - 2} y={H - 2} textAnchor="end" fontFamily="Archivo Narrow, Archivo, sans-serif"
          fontSize="3.4" fontWeight="600" letterSpacing="0.3" fill="#1B1F1A">OPP GOAL</text>
      </svg>

      <figcaption className="mt-3 max-w-read text-sm text-ink-soft">
        {view === 'touches'
          ? 'Shading is where the ball reaches them, their strongest zone against the rest. The scale is deliberately steep: a midfielder touches the ball almost everywhere, and a flat ramp hides where they actually live.'
          : `The ${Math.min(TOP_FLOWS, flows.length)} strongest links between zones, completed passes only. Line weight carries volume and the arrowhead is a fixed size, so the head never competes with it. A ring is circulation that stayed inside one zone.`}
        <span className="block mt-1 font-label text-label font-semibold uppercase text-ink-faint">
          {profile.passes_counted ?? 0} completed passes
          {profile.reliable === false && ' · thin sample, read the shape loosely'}
          {name ? ` · ${name}` : ''}
        </span>
      </figcaption>
    </figure>
  )
}

export default PitchMap
