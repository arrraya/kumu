"""
Kumü — Biomechanical metrics from 3D body pose trajectories
===========================================================

Adapted from MattLowrieDS/skillcorner_pose_viz (MIT), which reads
SkillCorner's open Body Pose dataset. Credit to Matt Lowrie for the
original implementation and to SkillCorner for the data.

WHAT CHANGED, AND WHY
---------------------
An audit of the original found eight defects, four of them in this
module. Each fix is marked below with the finding it closes. The common
thread is the one this codebase keeps meeting: a value that could only
ever come out one way, or a path that only works for the case its test
happens to cover.

  #1  The single-hip fallback returned garbage when a joint KEY was
      absent (as opposed to present-and-NaN). `~False` in Python is the
      integer -1, so `(~l_valid) & r_valid` produced an int array, which
      NumPy reads as POSITIONAL INDICES rather than a mask. Measured:
      hip orientation returned 1 finite value out of 40, at index 1;
      turning velocity returned none at all. The original's own test for
      this path passes, because it simulates occlusion by writing NaN
      into a key that exists. Fixed at the root: `_valid_xy` always
      returns a real boolean array of the right length.

  #2  Mean cadence averaged the per-interval rates, which is not the
      mean rate. By Jensen's inequality the arithmetic mean of 60/x is
      always >= 60/mean(x), so the figure was biased UPWARD, always:
      +12% on two intervals of 0.4s and 0.8s, +37% on 0.3/0.5/1.2. The
      original's tests use a perfectly periodic walker, where the two
      formulas agree exactly. Cadence is now steps over elapsed time.

  #3  `compute_stride_length` read `ALL_JOINTS[0]` - "nose" - purely to
      measure sequence length, so passing it only leg joints, which is
      all it uses and what its own docstring invites, raised KeyError.
      Every sibling function used `next(iter(...))`. Now so does this.

  #4  The default foot-height filter was the mean knee z OVER THE SAME
      SEQUENCE it filters. Standing, that is 0.45 m; sprinting, 0.64 m -
      the filter meant to exclude high kicks loosened exactly when the
      feet came up most. The default is now a declared constant, and the
      adaptive behaviour is available by asking for it.

Findings #5 to #8 live in the original's animator and loader; see
`loader.py` for those, and the audit document for #5, which concerns a
visualiser Kumü does not use.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import find_peaks, savgol_filter


# How high a foot may be and still count as a step contact.
#
# DECLARED, not measured. A knee is roughly half a metre off the ground
# on a standing adult, and a foot above that is doing something other
# than walking. The original derived this from the mean knee height of
# the very sequence being filtered, which made the threshold a function
# of the activity: the harder a player ran, the more it let through.
# A declared constant can be argued with; a circular one cannot.
DEFAULT_FOOT_HEIGHT_M = 0.50

# Physiological bounds, also declared.
MAX_CADENCE_SPM = 260.0
MAX_STEP_INTERVAL_S = 1.5


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _n_frames(joint_trajectories: Dict[str, np.ndarray]) -> int:
    """Sequence length, from whatever joint happens to be present.

    Finding #3: this used to read ALL_JOINTS[0] in one function, which
    demanded a "nose" key that function never used.
    """
    for arr in joint_trajectories.values():
        if arr is not None and len(arr) > 0:
            return len(arr)
    return 0


def _valid_xy(arr: Optional[np.ndarray], n_frames: int) -> np.ndarray:
    """A real boolean mask of length n_frames: which frames have x and y.

    Finding #1 in one function. The original wrote

        l_valid = (l_arr is not None) and (~np.isnan(...)) & (...)

    which is a Python `and`: it yields the ARRAY when the joint exists
    and the scalar `False` when it does not. Downstream, `~False` is -1,
    and `-1 & <bool array>` is an INT array that NumPy then treats as a
    list of positions to index. An absent joint did not disable a branch;
    it silently turned a mask into a scrambled index.

    Returning an all-False array of the right shape makes the absent case
    behave like the all-occluded case, which is what it means.
    """
    if arr is None:
        return np.zeros(n_frames, dtype=bool)
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != n_frames:
        return np.zeros(n_frames, dtype=bool)
    return (~np.isnan(a[:, 0])) & (~np.isnan(a[:, 1]))


def _as_array(arr: Optional[np.ndarray]) -> Optional[np.ndarray]:
    return None if arr is None else np.asarray(arr, dtype=np.float64)


def _segments(valid_indices: np.ndarray, max_gap: int = 2) -> List[Tuple[int, int]]:
    """Contiguous runs of valid frames, split where the gap exceeds max_gap."""
    if len(valid_indices) == 0:
        return []
    out = []
    start_i = 0
    for sp in np.where(np.diff(valid_indices) > max_gap)[0]:
        out.append((int(valid_indices[start_i]), int(valid_indices[sp])))
        start_i = sp + 1
    out.append((int(valid_indices[start_i]), int(valid_indices[-1])))
    return out


def _odd_window(requested: int, available: int) -> int:
    """Largest odd window no greater than either bound."""
    w = requested if requested % 2 == 1 else requested - 1
    cap = available if available % 2 == 1 else available - 1
    return min(w, cap)


# ---------------------------------------------------------------------------
# Stride
# ---------------------------------------------------------------------------

def compute_stride_length(
    joint_trajectories: Dict[str, np.ndarray],
    left_ankle_joint: str = "lAnkle",
    right_ankle_joint: str = "rAnkle",
    left_heel_joint: str = "lHeel",
    right_heel_joint: str = "rHeel",
    height_threshold_m: Optional[float] = None,
    adaptive_threshold: bool = False,
    unknown_height: str = "exclude",
) -> np.ndarray:
    """Per-frame foot-to-foot distance in the x/y pitch plane, in metres.

    Ankles are the contact point; heels stand in per frame when an ankle
    is missing. Frames where either foot is above `height_threshold_m`
    are NaN, so a high kick is not read as an enormous stride.

    Parameters
    ----------
    height_threshold_m
        Declared ceiling in metres. Defaults to DEFAULT_FOOT_HEIGHT_M.
    adaptive_threshold
        Opt in to the original's behaviour - the threshold taken from the
        sequence's own knee heights - but with the MEDIAN rather than the
        mean, which a few raised-knee frames cannot drag upward. Still
        circular, which is why it is not the default.
    unknown_height
        What to do with a frame whose x and y are known but whose z is
        not. "exclude" (default) drops it; "include" keeps it. Neither is
        obviously right, so it is a parameter rather than a silent
        choice, and `summarise_stride` reports how many frames it hit.
    """
    if unknown_height not in ("exclude", "include"):
        raise ValueError("unknown_height must be 'exclude' or 'include'")

    n_frames = _n_frames(joint_trajectories)
    stride_lengths = np.full(n_frames, np.nan, dtype=np.float64)
    if n_frames == 0:
        return stride_lengths

    def resolve_foot(ankle_name: str, heel_name: str):
        ankle = _as_array(joint_trajectories.get(ankle_name))
        heel = _as_array(joint_trajectories.get(heel_name))
        if ankle is None and heel is None:
            return None
        xs = np.full(n_frames, np.nan)
        ys = np.full(n_frames, np.nan)
        zs = np.full(n_frames, np.nan)
        if ankle is not None and ankle.shape[0] == n_frames:
            ok = (~np.isnan(ankle[:, 0])) & (~np.isnan(ankle[:, 1]))
            xs[ok], ys[ok], zs[ok] = ankle[ok, 0], ankle[ok, 1], ankle[ok, 2]
        if heel is not None and heel.shape[0] == n_frames:
            gap = np.isnan(xs) & (~np.isnan(heel[:, 0])) & (~np.isnan(heel[:, 1]))
            xs[gap], ys[gap], zs[gap] = heel[gap, 0], heel[gap, 1], heel[gap, 2]
        return xs, ys, zs

    left = resolve_foot(left_ankle_joint, left_heel_joint)
    right = resolve_foot(right_ankle_joint, right_heel_joint)
    if left is None or right is None:
        return stride_lengths

    lx, ly, lz = left
    rx, ry, rz = right

    threshold = _resolve_threshold(joint_trajectories, height_threshold_m, adaptive_threshold)

    both_xy = (~np.isnan(lx)) & (~np.isnan(ly)) & (~np.isnan(rx)) & (~np.isnan(ry))
    z_known = (~np.isnan(lz)) & (~np.isnan(rz))

    with np.errstate(invalid="ignore"):
        low_enough = (lz <= threshold) & (rz <= threshold)

    if unknown_height == "include":
        height_ok = np.where(z_known, low_enough, True)
    else:
        height_ok = low_enough & z_known

    valid = both_xy & height_ok
    if np.any(valid):
        dx = lx[valid] - rx[valid]
        dy = ly[valid] - ry[valid]
        stride_lengths[valid] = np.hypot(dx, dy)

    return stride_lengths


def _resolve_threshold(
    joint_trajectories: Dict[str, np.ndarray],
    height_threshold_m: Optional[float],
    adaptive: bool,
) -> float:
    """The foot-height ceiling actually used. Finding #4."""
    if height_threshold_m is not None:
        return float(height_threshold_m)
    if not adaptive:
        return DEFAULT_FOOT_HEIGHT_M

    knee_zs = []
    for kj in ("lKnee", "rKnee"):
        k = _as_array(joint_trajectories.get(kj))
        if k is None:
            continue
        ok = (~np.isnan(k[:, 0])) & (~np.isnan(k[:, 2]))
        if np.any(ok):
            knee_zs.append(k[ok, 2])
    if not knee_zs:
        return DEFAULT_FOOT_HEIGHT_M
    # Median, not mean: a handful of raised-knee frames should not lift
    # the ceiling for the whole sequence.
    return float(np.median(np.concatenate(knee_zs)))


# ---------------------------------------------------------------------------
# Steps and cadence
# ---------------------------------------------------------------------------

def compute_num_steps(
    joint_trajectories: Dict[str, np.ndarray],
    fps: float = 25.0,
    min_prominence_m: float = 0.07,
    min_speed_mps: float = 0.35,
    max_cadence_spm: float = MAX_CADENCE_SPM,
    max_step_interval_s: float = MAX_STEP_INTERVAL_S,
    smooth_window_frames: int = 9,
    left_ankle_joint: str = "lAnkle",
    right_ankle_joint: str = "rAnkle",
    left_heel_joint: str = "lHeel",
    right_heel_joint: str = "rHeel",
    height_threshold_m: Optional[float] = None,
    hip_joint: str = "midHip",
) -> Tuple[int, np.ndarray, float, Dict[str, object]]:
    """Foot strikes and cadence.

    Returns (total_steps, step_frames, cadence_spm, basis).

    The fourth element is new and is the point. The velocity gate - which
    rejects peaks while the player is standing still - needs a hip
    trajectory. When there is none the original filled the speed array
    with exactly the gate's own threshold, so every peak passed, and the
    caller was handed a step count with no sign that the gate had never
    run. `basis["speed_gate"]` now says whether it did.

    Cadence is steps over elapsed time (finding #2), not the mean of the
    per-interval rates.
    """
    n_frames = _n_frames(joint_trajectories)
    basis: Dict[str, object] = {
        "speed_gate": "not applied",
        "frames": n_frames,
        "foot_height_ceiling_m": _resolve_threshold(joint_trajectories, height_threshold_m, False),
    }
    if n_frames == 0:
        return 0, np.array([], dtype=int), 0.0, basis

    strides = compute_stride_length(
        joint_trajectories,
        left_ankle_joint=left_ankle_joint,
        right_ankle_joint=right_ankle_joint,
        left_heel_joint=left_heel_joint,
        right_heel_joint=right_heel_joint,
        height_threshold_m=height_threshold_m,
    )
    basis["stride_coverage"] = float(np.mean(~np.isnan(strides))) if n_frames else 0.0

    valid_indices = np.where(~np.isnan(strides))[0]
    if len(valid_indices) < max(5, smooth_window_frames):
        basis["speed_gate"] = "not applied: too few frames with a stride"
        return 0, np.array([], dtype=int), 0.0, basis

    # --- velocity gate -----------------------------------------------------
    hip = _as_array(joint_trajectories.get(hip_joint))
    hip_ok = _valid_xy(hip, n_frames)
    speed = None
    if np.sum(hip_ok) >= 2:
        idx = np.where(hip_ok)[0]
        dt_frames = np.diff(idx).astype(np.float64)
        dt_frames[dt_frames == 0] = 1.0
        inst = np.hypot(np.diff(hip[idx, 0]), np.diff(hip[idx, 1])) / (dt_frames / fps)
        raw = np.zeros(n_frames, dtype=np.float64)
        raw[idx[1:]] = inst
        raw[idx[0]] = inst[0]
        k = min(5, n_frames)
        speed = np.convolve(raw, np.ones(k) / k, mode="same")
        basis["speed_gate"] = "applied"
    else:
        basis["speed_gate"] = "not applied: no hip trajectory to measure speed from"

    # --- peak detection ----------------------------------------------------
    first_v, last_v = valid_indices[0], valid_indices[-1]
    segment = strides[first_v : last_v + 1].copy()
    seg_nan = np.isnan(segment)
    if np.any(seg_nan):
        x_axis = np.arange(len(segment))
        segment[seg_nan] = np.interp(x_axis[seg_nan], x_axis[~seg_nan], segment[~seg_nan])

    w_len = _odd_window(smooth_window_frames, len(segment))
    smoothed = savgol_filter(segment, window_length=w_len, polyorder=2) if w_len >= 5 else segment

    min_dist = max(3, int(np.floor(fps * 60.0 / max_cadence_spm)))
    peaks_rel, _ = find_peaks(smoothed, distance=min_dist, prominence=min_prominence_m)
    detected = peaks_rel + first_v

    if speed is None:
        step_frames = np.asarray(detected, dtype=int)
    else:
        step_frames = np.asarray([f for f in detected if speed[f] >= min_speed_mps], dtype=int)

    total_steps = int(len(step_frames))
    if total_steps < 2:
        return total_steps, step_frames, 0.0, basis

    # --- cadence: steps over elapsed time ----------------------------------
    #
    # Finding #2. The original returned mean(60 / intervals). For a rate,
    # the average over a period is total count over total time; averaging
    # the instantaneous rates weights short intervals far too heavily and,
    # by Jensen, can only ever overstate.
    intervals_s = np.diff(step_frames) / fps
    active = intervals_s[intervals_s <= max_step_interval_s]
    if len(active) == 0:
        cadence = 0.0
        basis["cadence_basis"] = "no interval short enough to count as locomotion"
    else:
        cadence = 60.0 * len(active) / float(np.sum(active))
        basis["cadence_basis"] = (
            "%d of %d intervals counted as active locomotion, over %.2f s"
            % (len(active), len(intervals_s), float(np.sum(active)))
        )

    return total_steps, step_frames, float(round(cadence, 2)), basis


# ---------------------------------------------------------------------------
# Angles
# ---------------------------------------------------------------------------

def compute_3point_angle(
    p1: np.ndarray,
    p2_vertex: np.ndarray,
    p3: np.ndarray,
    radians: bool = False,
) -> np.ndarray:
    """Planar angle at p2 between the rays p2->p1 and p2->p3.

    Computed in the 3D plane the three points span, so it does not depend
    on the camera. Unchanged from the original, which was correct.
    """
    p1 = np.asarray(p1, dtype=np.float64)
    p2 = np.asarray(p2_vertex, dtype=np.float64)
    p3 = np.asarray(p3, dtype=np.float64)

    v1, v2 = p1 - p2, p3 - p2
    dot = np.sum(v1 * v2, axis=-1)
    denom = np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1)

    with np.errstate(divide="ignore", invalid="ignore"):
        cosine = np.clip(dot / denom, -1.0, 1.0)
        angles = np.arccos(cosine)
        if not radians:
            angles = np.degrees(angles)
        angles = np.where(denom > 0, angles, np.nan)

    return angles


def compute_knee_angles(
    joint_trajectories: Dict[str, np.ndarray],
    radians: bool = False,
    angle_convention: str = "included",
    smooth_window_frames: Optional[int] = None,
    use_heel_fallback: bool = False,
    left_hip_joint: str = "lHip",
    left_knee_joint: str = "lKnee",
    left_ankle_joint: str = "lAnkle",
    left_heel_joint: str = "lHeel",
    right_hip_joint: str = "rHip",
    right_knee_joint: str = "rKnee",
    right_ankle_joint: str = "rAnkle",
    right_heel_joint: str = "rHeel",
) -> Dict[str, np.ndarray]:
    """Per-frame knee angle for each leg, from hip -> knee -> ankle.

    "included" is the angle behind the knee: 180 degrees straight.
    "flexion" is its complement: 0 degrees straight.
    """
    if angle_convention not in ("included", "flexion"):
        raise ValueError(
            "Unknown angle_convention: '%s'. Must be 'included' or 'flexion'." % angle_convention
        )

    n_frames = _n_frames(joint_trajectories)
    if n_frames == 0:
        empty = np.array([], dtype=np.float64)
        return {"left": empty, "right": empty}

    def resolve_distal(ankle_name: str, heel_name: str) -> Optional[np.ndarray]:
        ankle = _as_array(joint_trajectories.get(ankle_name))
        if not use_heel_fallback:
            return ankle
        heel = _as_array(joint_trajectories.get(heel_name))
        if ankle is None:
            return heel
        if heel is None:
            return ankle
        resolved = ankle.copy()
        missing = np.isnan(resolved[:, 0])
        resolved[missing] = heel[missing]
        return resolved

    def one_leg(hip_name, knee_name, ankle_name, heel_name) -> np.ndarray:
        hip = _as_array(joint_trajectories.get(hip_name))
        knee = _as_array(joint_trajectories.get(knee_name))
        distal = resolve_distal(ankle_name, heel_name)
        if hip is None or knee is None or distal is None:
            return np.full(n_frames, np.nan, dtype=np.float64)

        angles = compute_3point_angle(hip, knee, distal, radians=radians)
        if angle_convention == "flexion":
            angles = (np.pi if radians else 180.0) - angles

        if smooth_window_frames is not None and smooth_window_frames >= 3:
            ok = ~np.isnan(angles)
            if np.sum(ok) >= smooth_window_frames:
                idx = np.where(ok)[0]
                first_v, last_v = idx[0], idx[-1]
                seg = angles[first_v : last_v + 1].copy()
                seg_nan = np.isnan(seg)
                if np.any(seg_nan):
                    x_axis = np.arange(len(seg))
                    seg[seg_nan] = np.interp(x_axis[seg_nan], x_axis[~seg_nan], seg[~seg_nan])
                w_len = _odd_window(smooth_window_frames, len(seg))
                if w_len >= 3:
                    smoothed = savgol_filter(seg, window_length=w_len, polyorder=min(2, w_len - 1))
                    # Interpolation was a means to smooth, not a measurement:
                    # frames that had no angle get their NaN back.
                    angles[first_v : last_v + 1] = np.where(
                        ok[first_v : last_v + 1], smoothed, np.nan
                    )
        return angles

    return {
        "left": one_leg(left_hip_joint, left_knee_joint, left_ankle_joint, left_heel_joint),
        "right": one_leg(right_hip_joint, right_knee_joint, right_ankle_joint, right_heel_joint),
    }


# ---------------------------------------------------------------------------
# Pelvis
# ---------------------------------------------------------------------------

def _pelvic_vector(
    joint_trajectories: Dict[str, np.ndarray],
    n_frames: int,
    left_hip_joint: str,
    right_hip_joint: str,
    mid_hip_joint: str,
) -> np.ndarray:
    """The 3D right-hip -> left-hip vector per frame, NaN where unresolvable.

    Finding #1 lives here. Every mask below comes from `_valid_xy`, so an
    absent joint key behaves exactly like a fully occluded one instead of
    turning the next `~` into an integer.
    """
    l_arr = _as_array(joint_trajectories.get(left_hip_joint))
    r_arr = _as_array(joint_trajectories.get(right_hip_joint))
    m_arr = _as_array(joint_trajectories.get(mid_hip_joint))

    l_ok = _valid_xy(l_arr, n_frames)
    r_ok = _valid_xy(r_arr, n_frames)
    m_ok = _valid_xy(m_arr, n_frames)

    v = np.full((n_frames, 3), np.nan, dtype=np.float64)

    both = l_ok & r_ok
    if np.any(both):
        v[both] = l_arr[both] - r_arr[both]

    # Half a pelvis is still an orientation: midHip is the centre, so the
    # vector from it to one hip is half the full width.
    left_only = l_ok & (~r_ok) & m_ok
    if np.any(left_only):
        v[left_only] = 2.0 * (l_arr[left_only] - m_arr[left_only])

    right_only = (~l_ok) & r_ok & m_ok
    if np.any(right_only):
        v[right_only] = 2.0 * (m_arr[right_only] - r_arr[right_only])

    return v


def compute_hip_orientation(
    joint_trajectories: Dict[str, np.ndarray],
    radians: bool = False,
    left_hip_joint: str = "lHip",
    right_hip_joint: str = "rHip",
    mid_hip_joint: str = "midHip",
) -> np.ndarray:
    """Per-frame pelvic orientation in the x/y pitch plane.

    Degrees in (-180, 180], or radians. NaN where the hips cannot be
    resolved from either both hips or one hip plus midHip.
    """
    n_frames = _n_frames(joint_trajectories)
    if n_frames == 0:
        return np.array([], dtype=np.float64)

    v = _pelvic_vector(
        joint_trajectories, n_frames, left_hip_joint, right_hip_joint, mid_hip_joint
    )
    angles = np.full(n_frames, np.nan, dtype=np.float64)

    ok = (~np.isnan(v[:, 0])) & (~np.isnan(v[:, 1]))
    ok &= np.hypot(np.where(ok, v[:, 0], 0.0), np.where(ok, v[:, 1], 0.0)) > 1e-6
    if np.any(ok):
        raw = np.arctan2(v[ok, 1], v[ok, 0])
        angles[ok] = raw if radians else np.degrees(raw)

    return angles


def compute_turning_velocity(
    joint_trajectories: Dict[str, np.ndarray],
    fps: float = 25.0,
    radians: bool = False,
    absolute: bool = False,
    axis: str = "vertical",
    smooth_window_frames: Optional[int] = 7,
    left_hip_joint: str = "lHip",
    right_hip_joint: str = "rHip",
    mid_hip_joint: str = "midHip",
    neck_joint: str = "neck",
) -> np.ndarray:
    """Rate of rotation of the pelvis, in deg/s or rad/s.

    axis="vertical" measures yaw about the pitch normal. axis="spine"
    measures it about the midHip -> neck line, which tilts with the
    player. Phase is unwrapped so that crossing +/-180 degrees does not
    register as a spike, and the derivative is taken by Savitzky-Golay so
    that pose jitter is not differentiated into noise.

    NOTE on axis="spine": where the neck or midHip is missing, the axis
    falls back to vertical for those frames. That fallback is silent in
    the returned array by necessity - it is an ndarray - so a caller that
    needs to know should check neck coverage itself. `summarise_pose` in
    aggregate.py reports it.
    """
    if axis not in ("vertical", "spine"):
        raise ValueError("Unknown axis: '%s'. Must be 'vertical' or 'spine'." % axis)

    n_frames = _n_frames(joint_trajectories)
    if n_frames == 0:
        return np.array([], dtype=np.float64)

    dt = 1.0 / fps if fps > 0 else 1.0 / 25.0
    v = _pelvic_vector(
        joint_trajectories, n_frames, left_hip_joint, right_hip_joint, mid_hip_joint
    )
    v_ok = (~np.isnan(v[:, 0])) & (~np.isnan(v[:, 1]))
    out = np.full(n_frames, np.nan, dtype=np.float64)
    if not np.any(v_ok):
        return out

    if axis == "vertical":
        raw = np.full(n_frames, np.nan, dtype=np.float64)
        raw[v_ok] = np.arctan2(v[v_ok, 1], v[v_ok, 0])
        _fill_velocity(out, raw, v_ok, dt, smooth_window_frames)
    else:
        neck = _as_array(joint_trajectories.get(neck_joint))
        mid = _as_array(joint_trajectories.get(mid_hip_joint))
        axis_vecs = np.zeros((n_frames, 3), dtype=np.float64)
        axis_vecs[:, 2] = 1.0
        if neck is not None and mid is not None:
            spine = neck - mid
            lens = np.linalg.norm(spine, axis=1, keepdims=True)
            good = (~np.isnan(lens[:, 0])) & (lens[:, 0] > 1e-4)
            if np.any(good):
                axis_vecs[good] = spine[good] / lens[good]

        dot_a = np.sum(v * axis_vecs, axis=1, keepdims=True)
        v_perp = v - dot_a * axis_vecs
        perp_lens = np.linalg.norm(v_perp, axis=1, keepdims=True)
        u_ok = v_ok & (perp_lens[:, 0] > 1e-4)
        u = np.full((n_frames, 3), np.nan, dtype=np.float64)
        u[u_ok] = v_perp[u_ok] / perp_lens[u_ok]

        for seg_start, seg_end in _segments(np.where(u_ok)[0]):
            seg_len = seg_end - seg_start + 1
            if seg_len < 2:
                continue
            seg_u = u[seg_start : seg_end + 1]
            seg_axis = axis_vecs[seg_start : seg_end + 1]
            mask = ~np.isnan(seg_u[:, 0])
            if np.sum(mask) < 2:
                continue
            dtheta = np.zeros(seg_len, dtype=np.float64)
            for i in range(seg_len - 1):
                if not (mask[i] and mask[i + 1]):
                    continue
                avg = seg_axis[i] + seg_axis[i + 1]
                norm_a = np.linalg.norm(avg)
                avg = avg / norm_a if norm_a > 1e-4 else np.array([0.0, 0.0, 1.0])
                sin_dt = float(np.dot(np.cross(seg_u[i], seg_u[i + 1]), avg))
                cos_dt = float(np.dot(seg_u[i], seg_u[i + 1]))
                dtheta[i + 1] = np.arctan2(sin_dt, cos_dt)
            cum = np.cumsum(dtheta)
            w_len = _odd_window(smooth_window_frames or 0, seg_len) if smooth_window_frames else 0
            if w_len >= 3:
                seg_vel = savgol_filter(
                    cum, window_length=w_len, polyorder=min(2, w_len - 1), deriv=1, delta=dt
                )
            else:
                seg_vel = np.gradient(cum, dt)
            seg_vel[~mask] = np.nan
            out[seg_start : seg_end + 1] = seg_vel

    if not radians:
        out = np.degrees(out)
    if absolute:
        out = np.abs(out)
    return out


def _fill_velocity(out, raw, ok, dt, smooth_window_frames) -> None:
    """Unwrap, differentiate and write back, one contiguous segment at a time."""
    for seg_start, seg_end in _segments(np.where(~np.isnan(raw))[0]):
        seg_len = seg_end - seg_start + 1
        if seg_len < 2:
            continue
        seg = raw[seg_start : seg_end + 1].copy()
        mask = ~np.isnan(seg)
        if np.sum(mask) < 2:
            continue
        if np.any(~mask):
            x_ax = np.arange(seg_len)
            seg_unwrapped = np.interp(x_ax, x_ax[mask], np.unwrap(seg[mask]))
        else:
            seg_unwrapped = np.unwrap(seg)
        w_len = _odd_window(smooth_window_frames or 0, seg_len) if smooth_window_frames else 0
        if w_len >= 3:
            seg_vel = savgol_filter(
                seg_unwrapped, window_length=w_len, polyorder=min(2, w_len - 1), deriv=1, delta=dt
            )
        else:
            seg_vel = np.gradient(seg_unwrapped, dt)
        seg_vel[~mask] = np.nan
        out[seg_start : seg_end + 1] = seg_vel
