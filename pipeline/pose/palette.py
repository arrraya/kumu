"""
Kumü — Cancha tokens for anything rendered outside the browser
================================================================

The product's palette, repeated here so a clip, a chart and a screen
are recognisably the same thing. These are the values in
frontend/tailwind.config.js; when that file changes, this one does too.

The skeleton's left/right split reuses the series colours rather than
inventing a second scheme: clay is series A everywhere in Kumü, slate
is series B. A reader who has seen one of Kumü's charts already knows
what the two colours mean here.
"""

# Surfaces
PAPER = "#F2F1EA"
PAPER_CARD = "#FBFAF5"
PAPER_SUNK = "#E9E8DE"

# Type
INK = "#1B1F1A"
INK_SOFT = "#3A3D38"
INK_FAINT = "#5C5F56"

# Pitch
GRASS = "#C8CFBE"
GRASS_SHADE = "#9BA68C"
RULE = "#D8D7CC"
RULE_STRONG = "#B6B4A6"

# Series: left limbs take A, right limbs take B
CLAY = "#C25A3A"
CLAY_INK = "#A6462A"
SLATE = "#3A5A7A"
SLATE_INK = "#2F4A66"

# Provenance and warning
FLAG = "#8A5E14"
FLAG_MARK = "#B07A20"
LOSS = "#A3372B"

# Which colour a joint or a bone takes.
#
# Left is clay, right is slate, the spine and pelvis are ink, the head
# is the provenance amber. Depth in a 3D view is hard to read without
# this: two legs in one colour cross and the eye loses which is which.
SIDE = {
    "left": CLAY,
    "right": SLATE,
    "center": INK,
    "head": FLAG_MARK,
}

HEAD_JOINTS = {"nose", "neck", "lEye", "rEye", "lEar", "rEar"}


def side_of(joint: str) -> str:
    """left / right / center / head, from the joint's name."""
    if joint in HEAD_JOINTS:
        return "head"
    if joint.startswith("l") and len(joint) > 1 and joint[1].isupper():
        return "left"
    if joint.startswith("r") and len(joint) > 1 and joint[1].isupper():
        return "right"
    return "center"


def bone_colour(a: str, b: str) -> str:
    """A bone takes its side's colour; one that crosses the body is ink."""
    sa, sb = side_of(a), side_of(b)
    if sa == sb:
        return SIDE[sa]
    if "head" in (sa, sb) and "center" in (sa, sb):
        return SIDE["head"]
    return SIDE["center"]
