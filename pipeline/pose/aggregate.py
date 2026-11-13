"""
Kumü — from per-frame pose to the per-90 figures the product reads
===================================================================

`metrics.py` produces one value per frame. Kumü stores one value per 90
minutes, in `players.metrics["movement"]`, and the scouting report reads
exactly three keys from there:

    average_speed            km/h
    distance_covered_per_90  km per 90
    high_intensity_runs      count per 90

This module is the bridge. It is short, and nearly all of it is about
being honest, because turning four seconds of a broadcast into a per-90
figure is an extrapolation three times over.

THE THREE THINGS THAT MAKE THIS HARD
------------------------------------

1. DIFFERENTIATING POSE NOISE PRODUCES SPEED THAT IS NOT THERE.
   SkillCorner states midHip's accuracy as p90_mae = 10.06 cm. If that
   error is roughly normal, sigma is about 7.8 cm, and the difference of
   two independent frames carries sigma 11 cm. At 25 fps that is

       0.111 m / 0.04 s = 2.8 m/s = 10 km/h of pure noise.

   More than a jogging player's actual speed. Raw frame-to-frame
   differencing of this data does not measure movement, it measures the
   pose estimator. Positions are therefore smoothed before they are
   differentiated, the window is declared, and the residual noise floor
   is reported alongside every figure.

2. THE CAMERA FOLLOWS THE BALL, SO THE SAMPLE IS NOT RANDOM.
   Coverage on the open dataset runs about 31% of player-frames, and it
   is missing precisely when a player is off-screen - which correlates
   with being far from the ball, which correlates with moving less. Any
   per-90 figure extrapolated from observed frames is therefore biased
   UPWARD, and by an unknown amount. That is stated in the basis and
   cannot be corrected away from this data alone.

3. A PER-90 FIGURE FROM A FEW SECONDS IS NOT A MEASUREMENT.
   Extrapolating 4 seconds to 90 minutes multiplies by 1350. This module
   refuses below `MIN_OBSERVED_SECONDS` rather than return a number whose
   confidence interval is wider than its range.

Nothing here invents a value. When the inputs do not support a figure,
`summarise_movement` returns `movement: None`, which is what Kumü's
`_movement()` already expects and renders as the declared-absent panel.
"""

from typing import Dict, Optional

import numpy as np
from scipy.signal import savgol_coeffs, savgol_filter

try:
    from .metrics import _as_array, _valid_xy
except ImportError:  # run as a script
    from metrics import _as_array, _valid_xy


# --- declared parameters ---------------------------------------------------
#
# Every one of these is a judgement, not a measurement. They are named,
# gathered here, and reported in the basis so a reader can argue with
# them instead of discovering them.

# Smoothing window for position before differentiation, in frames.
# At 25 fps, 15 frames is 0.6 s, which brings the noise floor computed
# above from ~10 km/h down to roughly 1 km/h.
SMOOTH_WINDOW_FRAMES = 15

# Below this much observed time, no per-90 figure is produced at all.
MIN_OBSERVED_SECONDS = 60.0

# High-speed running threshold. 19.8 km/h is the convention most widely
# used in football physical reporting; it is a declared line, not a
# property of the player.
HIGH_INTENSITY_KMH = 19.8

# A burst must last at least this long to count as a run rather than a
# spike in the smoothed signal.
MIN_RUN_SECONDS = 1.0

# How far below the entry line the speed must fall before a run is
# considered over. Without this, a player sustaining a speed just above
# the threshold is counted as many separate runs while a faster one is
# counted as a single continuous effort.
HYSTERESIS_KMH = 2.0

# Stated accuracy of midHip, from SkillCorner's own schema.
MIDHIP_P90_MAE_M = 0.1006


def _noise_floor_kmh(fps: float, window: int) -> float:
    """How much apparent speed the pose error alone produces, in km/h.

    Computed from the filter, not estimated. A Savitzky-Golay derivative
    is a linear filter, so for white input noise of standard deviation
    sigma the output standard deviation is exactly sigma times the L2
    norm of its coefficients. Speed is the magnitude of a two-component
    vector, so at a true speed of zero the noise does not average out -
    it follows a Rayleigh distribution with mean sigma*sqrt(pi/2), which
    is the figure returned here.

    This replaces a first attempt that used a closed-form approximation
    with a fitted constant in it. A fudge factor in a number labelled
    "noise floor" is the same defect this codebase keeps removing: a
    value that looks measured and is not. The coefficients are available,
    so there is no reason to approximate them.
    """
    if window < 5 or window % 2 == 0:
        window = max(5, window - 1 if window % 2 == 0 else window)
    dt = 1.0 / fps if fps > 0 else 1.0 / 25.0
    coeffs = savgol_coeffs(window, polyorder=2, deriv=1, delta=dt)
    sigma_pos = MIDHIP_P90_MAE_M / 1.2816  # p90 of a half-normal -> sigma
    sigma_axis = sigma_pos * float(np.linalg.norm(coeffs))
    return float(sigma_axis * np.sqrt(np.pi / 2.0) * 3.6)


def speed_series(
    joint_trajectories: Dict[str, np.ndarray],
    fps: float = 25.0,
    hip_joint: str = "midHip",
    smooth_window_frames: int = SMOOTH_WINDOW_FRAMES,
) -> Dict[str, np.ndarray]:
    """Smoothed horizontal speed of the hip, in km/h, per frame.

    Returns {"speed_kmh", "observed"}: the series, NaN outside observed
    runs, and the boolean mask of frames that contributed.

    Only runs of CONSECUTIVE observed frames are differentiated. Across a
    gap, the straight line between two sightings is not the path the
    player took and the elapsed time is not the time they took to walk
    it, so such intervals are left out rather than guessed at.
    """
    hip = _as_array(joint_trajectories.get(hip_joint))
    n_frames = 0 if hip is None else len(hip)
    speed = np.full(n_frames, np.nan, dtype=np.float64)
    observed = np.zeros(n_frames, dtype=bool)
    if n_frames == 0:
        return {"speed_kmh": speed, "observed": observed}

    ok = _valid_xy(hip, n_frames)
    if not np.any(ok):
        return {"speed_kmh": speed, "observed": observed}

    idx = np.where(ok)[0]
    # Split into runs of consecutive frames.
    breaks = np.where(np.diff(idx) > 1)[0]
    starts = np.concatenate([[0], breaks + 1])
    ends = np.concatenate([breaks, [len(idx) - 1]])

    dt = 1.0 / fps
    for s, e in zip(starts, ends):
        run = idx[s : e + 1]
        if len(run) < 3:
            continue
        xs = hip[run, 0]
        ys = hip[run, 1]

        w = smooth_window_frames if smooth_window_frames % 2 == 1 else smooth_window_frames - 1
        w = min(w, len(run) if len(run) % 2 == 1 else len(run) - 1)
        if w >= 5:
            vx = savgol_filter(xs, window_length=w, polyorder=2, deriv=1, delta=dt)
            vy = savgol_filter(ys, window_length=w, polyorder=2, deriv=1, delta=dt)
        else:
            vx = np.gradient(xs, dt)
            vy = np.gradient(ys, dt)

        speed[run] = np.hypot(vx, vy) * 3.6
        observed[run] = True

    return {"speed_kmh": speed, "observed": observed}


def summarise_movement(
    joint_trajectories: Dict[str, np.ndarray],
    fps: float = 25.0,
    hip_joint: str = "midHip",
    smooth_window_frames: int = SMOOTH_WINDOW_FRAMES,
    min_observed_seconds: float = MIN_OBSERVED_SECONDS,
    high_intensity_kmh: float = HIGH_INTENSITY_KMH,
    min_run_seconds: float = MIN_RUN_SECONDS,
    total_match_frames: Optional[int] = None,
) -> Dict[str, object]:
    """The three movement figures Kumü reads, or a declared absence.

    Parameters
    ----------
    total_match_frames
        How many frames of match the window was drawn from, if known.
        Only used to report coverage; it never scales a figure.

    Returns
    -------
    {"movement": {...} | None, "basis": str, "coverage": {...}}

    `movement` is either all three keys or None, because Kumü's
    `_movement()` requires all three and declares the panel absent
    otherwise. A partial fill would be worse than none: it would put two
    real numbers beside a missing one and invite the reader to average.
    """
    series = speed_series(
        joint_trajectories, fps=fps, hip_joint=hip_joint,
        smooth_window_frames=smooth_window_frames,
    )
    speed = series["speed_kmh"]
    observed = series["observed"]

    n_frames = len(speed)
    n_observed = int(np.sum(observed))
    observed_seconds = n_observed / fps if fps > 0 else 0.0
    floor = _noise_floor_kmh(fps, smooth_window_frames)

    coverage = {
        "frames_in_window": n_frames,
        "frames_observed": n_observed,
        "observed_seconds": round(observed_seconds, 2),
        "window_coverage": round(n_observed / n_frames, 4) if n_frames else 0.0,
        "match_coverage": (
            round(n_observed / total_match_frames, 4)
            if total_match_frames else None
        ),
        "noise_floor_kmh": round(floor, 2),
        "smoothing_window_frames": smooth_window_frames,
    }

    if observed_seconds < min_observed_seconds:
        return {
            "movement": None,
            "coverage": coverage,
            "basis": (
                "Not assessed: %.1f s of this player was observed, and a per-90 "
                "figure is not extrapolated from less than %.0f s. Supply a longer "
                "window or a source with better coverage."
                % (observed_seconds, min_observed_seconds)
            ),
        }

    vals = speed[observed]
    mean_speed = float(np.mean(vals))

    # High-intensity runs: bursts above the declared line lasting at least
    # min_run_seconds, counted per 90 minutes of OBSERVED time.
    #
    # With hysteresis, and it matters more than it sounds. A single
    # threshold counted a player holding 20 km/h as SEVEN runs and one
    # holding 28 km/h as one, because at 20 the smoothed signal grazes
    # the 19.8 line and crosses it repeatedly: the faster player scored
    # fewer runs. A run therefore starts above the line and ends only
    # when the speed drops HYSTERESIS_KMH below it, which is how physical
    # reporting handles this everywhere.
    min_run_frames = max(1, int(round(min_run_seconds * fps)))
    exit_kmh = high_intensity_kmh - HYSTERESIS_KMH
    runs = 0
    current = 0
    in_run = False
    for i in range(n_frames):
        if not observed[i]:
            if in_run and current >= min_run_frames:
                runs += 1
            in_run, current = False, 0
            continue
        v = speed[i]
        if in_run:
            if v < exit_kmh:
                if current >= min_run_frames:
                    runs += 1
                in_run, current = False, 0
            else:
                current += 1
        elif v >= high_intensity_kmh:
            in_run, current = True, 1
    if in_run and current >= min_run_frames:
        runs += 1

    per_90 = (90.0 * 60.0) / observed_seconds
    distance_km = mean_speed * (observed_seconds / 3600.0)

    movement = {
        "average_speed": round(mean_speed, 2),
        "distance_covered_per_90": round(distance_km * per_90, 2),
        "high_intensity_runs": int(round(runs * per_90)),
    }

    basis = (
        "Measured over %.1f s of observed play (%.0f%% of the window), smoothed "
        "with a %d-frame window before differentiation; the pose error alone "
        "accounts for about %.1f km/h. Distance and runs are the observed rates "
        "scaled to 90 minutes, not a full-match measurement. The camera follows "
        "the ball, so a player is observed more while involved, which biases "
        "every figure here upward by an amount this source cannot quantify."
        % (
            observed_seconds,
            100.0 * coverage["window_coverage"],
            smoothing_or(smooth_window_frames),
            floor,
        )
    )

    return {"movement": movement, "coverage": coverage, "basis": basis}


def smoothing_or(window: int) -> int:
    """The window actually applied, for the basis line."""
    return window if window % 2 == 1 else window - 1
