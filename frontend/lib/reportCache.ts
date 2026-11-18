/**
 * The last report, kept so a glance at another tab does not throw it away.
 *
 * It used to be a bare `localStorage.setItem('currentReport', …)` read back
 * on mount with no questions asked: not whose report it was, and not when
 * it was made. So selecting another player and opening this tab showed the
 * previous player's report, and a report made before a figure changed went
 * on showing the old figure for as long as the browser kept it. On the day
 * the A-League anchor was corrected, a cached report still said €11.2M
 * where Kumü had started saying €900K.
 *
 * Stamped with the player it belongs to and the moment it was made, so
 * both questions have answers.
 */
const CACHE_KEY = 'currentReport'
const CACHE_TTL_MS = 6 * 60 * 60 * 1000

export type CachedReport = { playerId: string; savedAt: number; report: any }

export function saveReport(playerId: string | number, report: any) {
  try {
    window.localStorage.setItem(CACHE_KEY, JSON.stringify({
      playerId: String(playerId), savedAt: Date.now(), report,
    }))
  } catch {
    // A private window, or storage full. The report is on screen either
    // way; losing the cache costs a regeneration, not the work.
  }
}

export function loadReport(playerId: string | number | undefined | null) {
  try {
    const raw = window.localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Anything written by an older build has no stamp, so it cannot be
    // shown to belong to this player or to be recent. Drop it.
    if (!parsed || typeof parsed !== 'object' || !parsed.savedAt) {
      window.localStorage.removeItem(CACHE_KEY)
      return null
    }
    if (playerId != null && String(parsed.playerId) !== String(playerId)) return null
    if (Date.now() - parsed.savedAt > CACHE_TTL_MS) {
      window.localStorage.removeItem(CACHE_KEY)
      return null
    }
    return { ...parsed, stale: Date.now() - parsed.savedAt > 60 * 1000 } as
      CachedReport & { stale: boolean }
  } catch {
    return null
  }
}

export function clearReport() {
  try {
    window.localStorage.removeItem(CACHE_KEY)
  } catch {
    /* nothing to clear */
  }
}
