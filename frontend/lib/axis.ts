/**
 * Rounded bounds for a chart axis.
 *
 * Recharts reads `domain={['dataMin - 5', 'dataMax + 5']}` as an instruction
 * to do that arithmetic itself, in floating point, and then prints whatever
 * comes out down the side of the chart. K. Jelacic's match-by-match axis
 * carried a bottom tick of 61.699999999999996, clipped by the label width to
 * "999999994".
 *
 * It only appeared on his chart. Two other players with the same three
 * matches read cleanly, because the artefact needs the right decimals to
 * show up - which is the most misleading way for this to fail, since the
 * two clean charts are evidence that the broken one is a data problem.
 *
 * This had already been found once and fixed in Analytics, in place, with a
 * comment explaining it. PerformanceChart kept the broken version: the same
 * formula in two files, one of them corrected. Hence one function.
 */
export function paddedDomain(
  pad: number,
  step = 5,
  floorAtZero = true,
): [(dataMin: number) => number, (dataMax: number) => number] {
  return [
    (dataMin: number) => {
      const bajo = Math.floor((dataMin - pad) / step) * step;
      return floorAtZero ? Math.max(0, bajo) : bajo;
    },
    (dataMax: number) => Math.ceil((dataMax + pad) / step) * step,
  ];
}

/** Ticks that land on whole numbers, because the bounds above are multiples
 *  of `step`. Paired with `allowDecimals={false}` on the axis. */
export const wholeTick = (v: number) => String(Math.round(v));
