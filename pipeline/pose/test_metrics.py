"""
Kumü — tests for the corrected pose metrics.

These are not a reimplementation of the original suite, which passes and
is worth keeping. They cover the four boundaries the original's 33 tests
leave open, each one the exact condition under which an audited defect
appeared, plus the invariants the fixes have to preserve.

Run: python3 -m unittest test_metrics -v
"""

import unittest

import numpy as np

from metrics import (
    DEFAULT_FOOT_HEIGHT_M,
    _resolve_threshold,
    compute_3point_angle,
    compute_hip_orientation,
    compute_knee_angles,
    compute_num_steps,
    compute_stride_length,
    compute_turning_velocity,
)


def walker(n_frames: int, fps: float = 25.0, cadence_spm: float = 160.0, speed: float = 3.0):
    """A periodic walker: hips advancing, feet swinging out of phase."""
    t = np.arange(n_frames) / fps
    jt = {}
    hip_x = speed * t
    step_hz = cadence_spm / 60.0
    swing = 0.45 * np.sin(2 * np.pi * (step_hz / 2.0) * t)

    jt["midHip"] = np.stack([hip_x, np.zeros(n_frames), np.full(n_frames, 0.95)], axis=1)
    jt["lHip"] = np.stack([hip_x, np.full(n_frames, 0.1), np.full(n_frames, 0.95)], axis=1)
    jt["rHip"] = np.stack([hip_x, np.full(n_frames, -0.1), np.full(n_frames, 0.95)], axis=1)
    jt["lKnee"] = np.stack([hip_x, np.full(n_frames, 0.1), np.full(n_frames, 0.5)], axis=1)
    jt["rKnee"] = np.stack([hip_x, np.full(n_frames, -0.1), np.full(n_frames, 0.5)], axis=1)
    jt["lAnkle"] = np.stack([hip_x + swing, np.full(n_frames, 0.1), np.full(n_frames, 0.08)], axis=1)
    jt["rAnkle"] = np.stack([hip_x - swing, np.full(n_frames, -0.1), np.full(n_frames, 0.08)], axis=1)
    jt["lHeel"] = jt["lAnkle"].copy()
    jt["rHeel"] = jt["rAnkle"].copy()
    jt["neck"] = np.stack([hip_x, np.zeros(n_frames), np.full(n_frames, 1.45)], axis=1)
    return jt


class TestAbsentJointKey(unittest.TestCase):
    """Finding #1: a joint key that is ABSENT, not present-and-NaN.

    The original's own fallback test writes NaN into a key that exists,
    which exercises a different branch. With the key missing, `~False`
    became -1 and NumPy indexed by position: hip orientation returned one
    finite value out of forty, turning velocity none at all.
    """

    def setUp(self):
        self.n = 60
        fps = 25.0
        t = np.arange(self.n) / fps
        theta = np.radians(60.0) * t
        half = 0.2
        self.full = {
            "midHip": np.stack(
                [np.zeros(self.n), np.zeros(self.n), np.full(self.n, 0.9)], axis=1
            ),
            "lHip": np.stack(
                [half * np.cos(theta), half * np.sin(theta), np.full(self.n, 0.9)], axis=1
            ),
            "rHip": np.stack(
                [-half * np.cos(theta), -half * np.sin(theta), np.full(self.n, 0.9)], axis=1
            ),
        }

    def test_hip_orientation_without_left_hip_key(self):
        partial = {k: v for k, v in self.full.items() if k != "lHip"}
        angles = compute_hip_orientation(partial)
        finite = int(np.sum(~np.isnan(angles)))
        self.assertEqual(
            finite, self.n,
            "every frame resolves from rHip + midHip; got %d of %d" % (finite, self.n),
        )

    def test_hip_orientation_without_right_hip_key(self):
        partial = {k: v for k, v in self.full.items() if k != "rHip"}
        angles = compute_hip_orientation(partial)
        self.assertEqual(int(np.sum(~np.isnan(angles))), self.n)

    def test_single_hip_matches_both_hips(self):
        """Half a pelvis points the same way as a whole one."""
        both = compute_hip_orientation(self.full)
        left_only = compute_hip_orientation({k: v for k, v in self.full.items() if k != "rHip"})
        np.testing.assert_allclose(both, left_only, atol=1e-9)

    def test_turning_velocity_without_a_hip_key(self):
        partial = {k: v for k, v in self.full.items() if k != "lHip"}
        vel = compute_turning_velocity(partial, fps=25.0)
        inner = vel[5:-5]
        self.assertEqual(int(np.sum(np.isnan(inner))), 0, "no frame should be NaN")
        self.assertAlmostEqual(float(np.mean(inner)), 60.0, delta=2.5)

    def test_no_hips_at_all_is_all_nan_not_a_crash(self):
        angles = compute_hip_orientation({"neck": np.zeros((self.n, 3))})
        self.assertEqual(len(angles), self.n)
        self.assertTrue(np.all(np.isnan(angles)))


class TestCadenceIsARate(unittest.TestCase):
    """Finding #2: cadence must be steps over time, never the mean of rates."""

    def test_uneven_intervals_are_not_overstated(self):
        # Strikes at 0.0, 0.4, 1.2 s -> two intervals, 0.4 and 0.8.
        # Steps over time: 2 / 1.2 s = 100.0 spm.
        # Mean of rates (the old way): (150 + 75) / 2 = 112.5 spm.
        fps = 25.0
        jt = walker(200, fps=fps)
        # Drive the assertion through the public function by checking the
        # identity it must satisfy, rather than hand-placing peaks.
        total, frames, cadence, basis = compute_num_steps(jt, fps=fps)
        self.assertGreaterEqual(total, 2)
        intervals = np.diff(frames) / fps
        active = intervals[intervals <= 1.5]
        expected = 60.0 * len(active) / float(np.sum(active))
        self.assertAlmostEqual(cadence, round(expected, 2), places=2)

    def test_matches_closed_form_for_a_periodic_walker(self):
        fps = 25.0
        for target in (120.0, 160.0, 200.0):
            jt = walker(250, fps=fps, cadence_spm=target)
            _, _, cadence, _ = compute_num_steps(jt, fps=fps)
            self.assertAlmostEqual(
                cadence, target, delta=target * 0.08,
                msg="cadence %.1f is not within 8%% of %.1f" % (cadence, target),
            )

    def test_jensen_direction(self):
        """Whatever the intervals, the old formula can only overstate."""
        rng = np.random.default_rng(11)
        for _ in range(200):
            iv = rng.uniform(0.25, 1.4, size=rng.integers(2, 12))
            old = float(np.mean(60.0 / iv))
            correct = 60.0 * len(iv) / float(np.sum(iv))
            self.assertGreaterEqual(old + 1e-9, correct)


class TestLegJointsOnly(unittest.TestCase):
    """Finding #3: the function may not demand a joint it never uses."""

    def test_stride_with_only_feet(self):
        n = 40
        jt = {
            "lAnkle": np.stack([np.zeros(n), np.full(n, 0.1), np.full(n, 0.05)], axis=1),
            "rAnkle": np.stack([np.full(n, 0.6), np.full(n, -0.1), np.full(n, 0.05)], axis=1),
        }
        strides = compute_stride_length(jt)
        self.assertEqual(len(strides), n)
        np.testing.assert_allclose(strides, np.hypot(0.6, 0.2), atol=1e-9)

    def test_num_steps_with_only_feet(self):
        jt = {k: v for k, v in walker(120).items() if k in ("lAnkle", "rAnkle")}
        total, frames, cadence, basis = compute_num_steps(jt)
        self.assertIsInstance(total, int)
        self.assertIn("no hip trajectory", str(basis["speed_gate"]))

    def test_empty_input(self):
        self.assertEqual(len(compute_stride_length({})), 0)
        self.assertEqual(compute_num_steps({})[0], 0)


class TestDeclaredThreshold(unittest.TestCase):
    """Finding #4: the foot-height ceiling must not move with the activity."""

    def _knees_at(self, n, z):
        jt = walker(n)
        jt["lKnee"][:, 2] = z
        jt["rKnee"][:, 2] = z
        return jt

    def test_default_is_constant_across_activities(self):
        quiet = compute_stride_length(self._knees_at(80, 0.45))
        busy = compute_stride_length(self._knees_at(80, 0.95))
        np.testing.assert_allclose(quiet, busy, atol=1e-12)

    def test_adaptive_is_opt_in_and_uses_the_median(self):
        n = 80
        jt = walker(n)
        jt["lKnee"][:, 2] = 0.45
        jt["rKnee"][:, 2] = 0.45
        jt["lKnee"][:8, 2] = 3.0  # a handful of extreme frames

        # Opting in reads the sequence; the default does not.
        self.assertEqual(_resolve_threshold(jt, None, False), DEFAULT_FOOT_HEIGHT_M)
        adaptive = _resolve_threshold(jt, None, True)

        # The median ignores the outliers. The original's mean would have
        # been dragged to about 0.61 by those eight frames.
        self.assertAlmostEqual(adaptive, 0.45, places=9)
        all_knee_z = np.concatenate([jt["lKnee"][:, 2], jt["rKnee"][:, 2]])
        self.assertGreater(float(np.mean(all_knee_z)), adaptive + 0.1)

    def test_explicit_threshold_wins_over_both(self):
        jt = walker(40)
        self.assertEqual(_resolve_threshold(jt, 0.33, True), 0.33)
        self.assertEqual(_resolve_threshold(jt, 0.33, False), 0.33)

    def test_high_foot_is_excluded(self):
        n = 20
        jt = {
            "lAnkle": np.stack([np.zeros(n), np.zeros(n), np.full(n, 0.05)], axis=1),
            "rAnkle": np.stack([np.full(n, 0.5), np.zeros(n), np.full(n, 0.05)], axis=1),
        }
        jt["rAnkle"][10:, 2] = DEFAULT_FOOT_HEIGHT_M + 0.4
        strides = compute_stride_length(jt)
        self.assertEqual(int(np.sum(~np.isnan(strides[:10]))), 10)
        self.assertEqual(int(np.sum(~np.isnan(strides[10:]))), 0)

    def test_unknown_height_is_a_choice_not_a_default(self):
        n = 20
        jt = {
            "lAnkle": np.stack([np.zeros(n), np.zeros(n), np.full(n, 0.05)], axis=1),
            "rAnkle": np.stack([np.full(n, 0.5), np.zeros(n), np.full(n, np.nan)], axis=1),
        }
        self.assertEqual(int(np.sum(~np.isnan(compute_stride_length(jt)))), 0)
        kept = compute_stride_length(jt, unknown_height="include")
        self.assertEqual(int(np.sum(~np.isnan(kept))), n)
        with self.assertRaises(ValueError):
            compute_stride_length(jt, unknown_height="maybe")


class TestVelocityGateIsDeclared(unittest.TestCase):
    """The gate that silently never ran now says so."""

    def test_gate_applied_with_a_hip(self):
        _, _, _, basis = compute_num_steps(walker(120))
        self.assertEqual(basis["speed_gate"], "applied")

    def test_gate_absent_without_a_hip(self):
        jt = {k: v for k, v in walker(120).items() if k != "midHip"}
        _, _, _, basis = compute_num_steps(jt)
        self.assertTrue(str(basis["speed_gate"]).startswith("not applied"))

    def test_stationary_player_registers_no_steps(self):
        n = 150
        rng = np.random.default_rng(3)
        jt = walker(n, speed=0.0)
        jt["midHip"][:, 0] = 5.0 + 0.004 * rng.standard_normal(n)
        jt["midHip"][:, 1] = 10.0 + 0.004 * rng.standard_normal(n)
        total, _, cadence, _ = compute_num_steps(jt)
        self.assertEqual(total, 0)
        self.assertEqual(cadence, 0.0)


class TestPreservedBehaviour(unittest.TestCase):
    """The fixes must not have broken what already worked."""

    def test_three_point_angle_right_angle(self):
        a = compute_3point_angle(
            np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
        )
        self.assertAlmostEqual(float(a), 90.0, places=9)

    def test_three_point_angle_degenerate_is_nan(self):
        a = compute_3point_angle(
            np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
        )
        self.assertTrue(np.isnan(a))

    def test_knee_conventions_are_complementary(self):
        jt = walker(60)
        inc = compute_knee_angles(jt, angle_convention="included")["left"]
        flx = compute_knee_angles(jt, angle_convention="flexion")["left"]
        np.testing.assert_allclose(inc + flx, 180.0, atol=1e-9)

    def test_knee_smoothing_restores_nan_where_there_was_no_angle(self):
        jt = walker(60)
        jt["lKnee"][20:25] = np.nan
        out = compute_knee_angles(jt, smooth_window_frames=7)["left"]
        self.assertTrue(np.all(np.isnan(out[20:25])))

    def test_turning_velocity_constant_spin(self):
        n, fps = 80, 25.0
        t = np.arange(n) / fps
        theta = np.radians(90.0) * t
        half = 0.2
        jt = {
            "midHip": np.stack([np.zeros(n), np.zeros(n), np.full(n, 0.9)], axis=1),
            "lHip": np.stack([half * np.cos(theta), half * np.sin(theta), np.full(n, 0.9)], axis=1),
            "rHip": np.stack([-half * np.cos(theta), -half * np.sin(theta), np.full(n, 0.9)], axis=1),
        }
        vel = compute_turning_velocity(jt, fps=fps)
        self.assertAlmostEqual(float(np.nanmean(vel[5:-5])), 90.0, delta=1.0)

    def test_turning_velocity_no_spike_at_the_branch_cut(self):
        n, fps = 100, 25.0
        t = np.arange(n) / fps
        theta = np.pi - 0.5 + np.radians(120.0) * t  # crosses +/- pi
        half = 0.2
        jt = {
            "midHip": np.stack([np.zeros(n), np.zeros(n), np.full(n, 0.9)], axis=1),
            "lHip": np.stack([half * np.cos(theta), half * np.sin(theta), np.full(n, 0.9)], axis=1),
            "rHip": np.stack([-half * np.cos(theta), -half * np.sin(theta), np.full(n, 0.9)], axis=1),
        }
        vel = compute_turning_velocity(jt, fps=fps)
        self.assertLess(float(np.nanmax(np.abs(vel[5:-5]))), 200.0)

    def test_invalid_arguments_raise(self):
        with self.assertRaises(ValueError):
            compute_turning_velocity(walker(30), axis="diagonal")
        with self.assertRaises(ValueError):
            compute_knee_angles(walker(30), angle_convention="bent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
