/**
 * One way to print a fee, matching the backend exactly.
 *
 * Six components divided by a million and showed one decimal, so every
 * figure under €1M collapsed. Z. Clough's negotiation read opening €0.8M,
 * target €0.9M, maximum €0.9M: the target and the walk-away printed as the
 * same number, which reads as a negotiation with no room in it. They are
 * €823K and €987K. Elsewhere on the same screen the Compatible Teams card
 * showed €823K correctly, because that one component had its own
 * formatter — so the same fee appeared twice, in two shapes, two panels
 * apart.
 *
 * This mirrors `_fmt_money` in the report generator line for line. The
 * backend prints the fee into its own sentences and the frontend prints it
 * into the tiles beside them, and a reader comparing the two is entitled
 * to see one number.
 */
export function formatMoney(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return '—';
  }
  if (value >= 1e6) {
    return `€${(value / 1e6).toFixed(1)}M`;
  }
  return `€${Math.round(value / 1e3)}K`;
}
