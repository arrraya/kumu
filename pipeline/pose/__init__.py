"""
Kumü — body pose processing.

Turns 3D joint trajectories into the per-90 movement figures the
scouting report reads, and declares what it could not measure.

Adapted from MattLowrieDS/skillcorner_pose_viz (MIT) with eight audited
defects corrected; see metrics.py for which, and why each one mattered.
Credit to Matt Lowrie for the original and to SkillCorner for the data.

    from pipeline.pose.aggregate import summarise_movement
    result = summarise_movement(joint_trajectories, fps=25.0)
    result["movement"]   # the three keys, or None
    result["basis"]      # why, in words
    result["coverage"]   # what fraction of the window was observed
"""

from .aggregate import speed_series, summarise_movement
from .metrics import (
    compute_3point_angle,
    compute_hip_orientation,
    compute_knee_angles,
    compute_num_steps,
    compute_stride_length,
    compute_turning_velocity,
)

__all__ = [
    "summarise_movement",
    "speed_series",
    "compute_stride_length",
    "compute_num_steps",
    "compute_3point_angle",
    "compute_knee_angles",
    "compute_hip_orientation",
    "compute_turning_velocity",
]
