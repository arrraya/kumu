'use client'

/**
 * The measurement, moving.
 *
 * The physical profile states that a player covers 12.2 km per 90 at
 * 8.1 km/h average. This is that player, in the match those figures came
 * from, at the fastest four seconds he was observed for — so the claim
 * and the thing it describes sit on the same page.
 *
 * One match of body pose is 3.3 GB open, which cannot live on the
 * application server, so nothing can cut a clip when somebody opens a
 * report. They are cut by `pipeline/pose/clips.py`, written into
 * `public/clips`, and listed in a manifest beside them. A player with no
 * entry gets no panel: the same absence the rest of this report already
 * knows how to state, rendered as nothing rather than as an apology.
 *
 * The manifest is keyed by the provider's player id and carries the
 * `external_id` each player holds inside Kumü, because that is what the
 * API hands the page. Matching on name would have worked today and
 * broken on the first player who shares one.
 */

import React, { useEffect, useState } from 'react'

type ClipEntry = {
  file: string
  name?: string | null
  external_id?: string | null
  frames?: number
  seconds?: number
  peak_kmh?: number
}

type Manifest = Record<string, ClipEntry>

// Fetched once per page rather than per player: it is a few hundred bytes
// and every panel asks the same question of it.
let cached: Promise<Manifest> | null = null

function loadManifest(): Promise<Manifest> {
  if (!cached) {
    cached = fetch('/clips/manifest.json')
      .then((r) => (r.ok ? r.json() : {}))
      // A missing manifest is the ordinary case for a deployment with no
      // clips in it, not a failure worth showing anybody.
      .catch(() => ({} as Manifest))
  }
  return cached
}

export default function PoseClip({
  externalId,
  playerName,
}: {
  externalId?: string | null
  playerName?: string | null
}) {
  const [entry, setEntry] = useState<ClipEntry | null>(null)

  useEffect(() => {
    let alive = true
    loadManifest().then((manifest) => {
      if (!alive) return
      const found = Object.values(manifest).find(
        (e) => e.external_id && e.external_id === externalId
      )
      setEntry(found ?? null)
    })
    return () => {
      alive = false
    }
  }, [externalId])

  if (!entry) return null

  return (
    <div className="bg-paper-card border border-rule rounded-sm p-6">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <h3 className="text-xl font-semibold m-0">Measured movement</h3>
        <span className="label">
          SkillCorner body pose · 25 fps · measured
        </span>
      </div>

      <p className="text-sm text-ink-soft max-w-read mt-3">
        The fastest {entry.seconds ?? 4} seconds {playerName ?? 'this player'} was
        observed for, from the match the figures below were measured in.
      </p>

      <video
        className="w-full mt-5 border border-rule rounded-sm bg-paper"
        src={`/clips/${entry.file}`}
        autoPlay
        loop
        muted
        playsInline
        preload="metadata"
      />

      <div className="flex items-baseline gap-6 mt-4 flex-wrap">
        {typeof entry.peak_kmh === 'number' && (
          <div>
            <span className="figure">{entry.peak_kmh.toFixed(1)}</span>
            <span className="label ml-2">km/h peak</span>
          </div>
        )}
        {typeof entry.frames === 'number' && (
          <span className="label">{entry.frames} frames</span>
        )}
      </div>

      {/* The same caution the athletic scores carry, in the place a reader
          is most likely to forget it: a clip looks like a measurement of
          the whole match and is four seconds of one. */}
      <p className="text-sm text-ink-soft max-w-read mt-4">
        One run, not a summary. The camera follows the ball, so a player is
        filmed more while involved — enough for the speed and distance
        beside this, not enough to count his sprints.
      </p>
    </div>
  )
}
