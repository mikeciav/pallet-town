"""
Pallet optimization engine.

Uses row/column stripe enumeration to find the optimal Ti (cartons per layer)
for uniform rectangular boxes on a rectangular pallet. Boxes can be rotated 90°
on the vertical axis (height never changes). This approach is O(n) where n is
the number of possible row splits — effectively instant for any real pallet.

Research note: general 2D bin packing is NP-hard, but for UNIFORM boxes the
optimal solution can almost always be found by trying all two-stripe patterns
(n rows of orientation A + remaining rows of orientation B). This covers block,
uniform, and most mixed patterns used in practice.
"""

from __future__ import annotations
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


def _D(x) -> Decimal:
    """Convert a number to Decimal via string to avoid inheriting float imprecision."""
    return Decimal(str(x))


def find_optimal_arrangement(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
) -> Tuple[int, Optional[Dict]]:
    """
    Find maximum Ti and the arrangement config that achieves it.

    Tries all stripe patterns over both pallet dimensions with both carton
    orientations: n stripes of A + remaining space filled with B stripes.
    """
    case_l, case_w, pallet_l, pallet_w = _D(case_l), _D(case_w), _D(pallet_l), _D(pallet_w)

    if case_l <= 0 or case_w <= 0 or pallet_l <= 0 or pallet_w <= 0:
        return 0, None

    best_ti = 0
    best_config: Optional[Dict] = None

    # Natural orientation A = (case_l × case_w); B is 90° rotation.
    # We enumerate both choices of "primary" orientation so that all
    # combinations are covered without explicit A/B labelling confusion.
    for a_l, a_w in [(case_l, case_w), (case_w, case_l)]:
        b_l, b_w = a_w, a_l  # 90° rotation

        # --- Row stripes: split along pallet WIDTH ---
        max_a = int(pallet_w / a_w)
        for n_a in range(max_a + 1):
            remaining = pallet_w - n_a * a_w
            n_b = int(remaining / b_w) if b_w > 0 else 0

            per_a = int(pallet_l / a_l) if a_l > 0 else 0
            per_b = int(pallet_l / b_l) if b_l > 0 else 0

            ti = n_a * per_a + n_b * per_b
            if ti > best_ti:
                best_ti = ti
                best_config = _make_config(
                    "row", float(pallet_l), float(pallet_w),
                    n_a, per_a, float(a_l), float(a_w),
                    n_b, per_b, float(b_l), float(b_w),
                    float(case_l), float(case_w),
                )

        # --- Column stripes: split along pallet LENGTH ---
        max_a = int(pallet_l / a_l)
        for n_a in range(max_a + 1):
            remaining = pallet_l - n_a * a_l
            n_b = int(remaining / b_l) if b_l > 0 else 0

            per_a = int(pallet_w / a_w) if a_w > 0 else 0
            per_b = int(pallet_w / b_w) if b_w > 0 else 0

            ti = n_a * per_a + n_b * per_b
            if ti > best_ti:
                best_ti = ti
                best_config = _make_config(
                    "col", float(pallet_l), float(pallet_w),
                    n_a, per_a, float(a_l), float(a_w),
                    n_b, per_b, float(b_l), float(b_w),
                    float(case_l), float(case_w),
                )

    return best_ti, best_config


def _make_config(
    split: str,
    pallet_l: float, pallet_w: float,
    n_a: int, per_a: int, a_l: float, a_w: float,
    n_b: int, per_b: int, b_l: float, b_w: float,
    orig_l: float, orig_w: float,
) -> dict:
    # rotated=True when the carton footprint is swapped from its original dims
    rot_a = not (a_l == orig_l and a_w == orig_w)
    rot_b = not rot_a
    return {
        "split": split,
        "pallet_l": pallet_l,
        "pallet_w": pallet_w,
        "a": {"count": n_a, "per_stripe": per_a, "l": a_l, "w": a_w, "rotated": rot_a},
        "b": {"count": n_b, "per_stripe": per_b, "l": b_l, "w": b_w, "rotated": rot_b},
    }



def find_shoppable_v2(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
    sides: int,
) -> Dict:

    case_l, case_w, pallet_l, pallet_w = _D(case_l), _D(case_w), _D(pallet_l), _D(pallet_w)

    if case_l > case_w:
        case_l, case_w = case_w, case_l  # Ensure case_l is the smaller dimension for consistent orientation
    """
    Corner-spiral shoppable arrangement — counts TI from generated positions.
    """
    pallet_area = pallet_l * pallet_w
    case_area = case_l * case_w
    min_box = case_l + case_w

    if pallet_w < min_box or pallet_l < min_box:
        std_ti, _ = find_optimal_arrangement(case_l, case_w, pallet_l, pallet_w)
        void_pct = max(_D('0'), (pallet_area - std_ti * case_area) / pallet_area)
        return {"ti": std_ti, "mode": "standard", "void_pct": round(float(void_pct), 4), "error": None}
    variants = [
        generate_shoppable_v2_positions(case_l, case_w, pallet_l, pallet_w, sides),
        generate_shoppable_v2_positions(case_w, case_l, pallet_w, pallet_l, sides)
    ]
    positions = max(variants, key=len)

    total_ti = len(positions)
    void_pct = max(_D('0'), (pallet_area - total_ti * case_area) / pallet_area)
    return {
        "ti": total_ti,
        "mode": "shoppable_spiral",
        "void_pct": round(float(void_pct), 4),
        "error": None,
    }


def generate_shoppable_v2_positions(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
    sides: int,
) -> List[Dict]:
    """
    Corner-spiral shoppable arrangement.

    Clockwise from top-left corner, 4 sides per loop:
      TOP    (→): n regular cases (case_w × case_l deep) + corner case (case_l × case_w deep)
      RIGHT  (↑): n regular cases (case_l × case_w)      + corner case (case_w × case_l deep)
      BOTTOM (←): n regular cases (case_w × case_l deep) + corner case (case_l × case_w deep)
      LEFT   (↓): n regular cases (case_l × case_w)      — no trailing corner

    Each regular case has its label face (case_l) perpendicular to the nearest wall.
    Corner cases bridge to the next side: case_l runs parallel, case_w is the depth.
    Bounding box shrinks by case_l after each full loop.

    Coordinates: x = W direction (0→pallet_w), y = L direction (0→pallet_l).
    """
    case_l, case_w, pallet_l, pallet_w = _D(case_l), _D(case_w), _D(pallet_l), _D(pallet_w)

    positions: List[Dict] = []

    # The bounding box shrinks inward by case_l on each side after every completed spiral pass.
    left_x   = _D('0')
    top_y    = _D('0')
    right_x  = pallet_w
    bottom_y = pallet_l

    # Primary algorithm to place cases in a spiral pattern
    while True:
        if 2 * case_l > right_x - left_x or 2 * case_l > bottom_y - top_y:
            # Not enough room for another full spiral loop with corners.
            # Move on to filling the chimney.
            break

        # ── TOP side (traveling in the +x direction) ──────────────────────
        # Regular top cases stand case_l deep (into the pallet) and case_w wide (along the wall).
        # They pack from the left wall rightward, reserving space for one corner case at the end.
        num_top_cases = max(0, int((right_x - left_x - case_l) / case_w))
        for i in range(num_top_cases):
            positions.append({
                "x": float(left_x + i * case_w),
                "y": float(top_y),
                "w": float(case_w), "h": float(case_l), "side": "top",
            })

        old_right_x = right_x
        right_x = left_x + num_top_cases * case_w + case_l  # right edge of the last regular top case + case_l for the corner

        # ── RIGHT side (traveling in the +y direction) ──────────────────────
        # Regular right cases stand case_l deep (into the pallet) and case_w tall (along the wall).
        # The column starts above the top corner and leaves room for one corner case at the bottom.
        if sides > 2:
            num_right_cases = max(0, int((bottom_y - top_y - case_l) / case_w))
        else:
            num_right_cases = max(0, int((bottom_y - top_y) / case_w))
        for i in range(num_right_cases):
            positions.append({
                "x": float(right_x - case_l),
                "y": float(top_y + i * case_w),
                "w": float(case_l), "h": float(case_w), "side": "right",
            })

        if sides > 2:
            bottom_y = top_y + num_right_cases * case_w + case_l  # bottom edge of the last regular right case + case_l for the corner

            # ── BOTTOM side (traveling in the -x direction) ───────────────────────
            # Regular bottom cases stand case_l deep and case_w wide, packed right-to-left.
            # The row's right edge is the inner face of the right corner (right_x - case_w).
            if sides > 3:
                num_bottom_cases = num_top_cases
            else:
                num_bottom_cases = max(0, int((old_right_x - left_x) / case_w))
            for i in range(num_bottom_cases):
                positions.append({
                    "x": float(right_x - (i + 1) * case_w),
                    "y": float(bottom_y - case_l),
                    "w": float(case_w), "h": float(case_l), "side": "bottom",
                })

            if sides > 3:
                # ── LEFT side (traveling in the -y direction) ───────────────────────
                # Regular left cases stand case_l deep and case_w tall, packed bottom-to-top.
                # No trailing corner — the left side terminates where the next loop's top row begins.
                num_left_cases = num_right_cases
                for i in range(num_left_cases):
                    positions.append({
                        "x": float(left_x),
                        "y": float(bottom_y - (i + 1) * case_w),
                        "w": float(case_l), "h": float(case_w), "side": "left",
                    })

        # Shrink the bounding box inward by case_l for the next loop.
        if sides > 3:
            left_x += case_l
        top_y += case_l
        right_x -= case_l
        if sides > 2:
            bottom_y -= case_l

    # Chimney fill algorithm
    if right_x - left_x > case_l:
        num_right_cases = max(0, int((bottom_y - top_y) / case_w))
        for i in range(num_right_cases):
            positions.append({
                "x": float(right_x - case_l),
                "y": float(top_y + i * case_w),
                "w": float(case_l), "h": float(case_w), "side": "right",
            })
        right_x -= case_l

    num_top_cases = max(0, int((right_x - left_x) / case_w))
    while top_y + case_l <= bottom_y:
        for i in range(num_top_cases):
            positions.append({
                "x": float(right_x - (i+1) * case_w),
                "y": float(top_y),
                "w": float(case_w), "h": float(case_l), "side": "top",
            })
        top_y += case_l

    return positions


def generate_positions(config: Dict) -> List[Dict]:
    """Return carton footprint positions for top-down SVG visualization."""
    if not config:
        return []

    positions: List[Dict] = []
    a = config["a"]
    b = config["b"]

    if config["split"] == "row":
        y = 0.0
        for _ in range(a["count"]):
            for col in range(a["per_stripe"]):
                positions.append({"x": col * a["l"], "y": y,
                                   "w": a["l"], "h": a["w"], "rotated": a["rotated"]})
            y += a["w"]
        for _ in range(b["count"]):
            for col in range(b["per_stripe"]):
                positions.append({"x": col * b["l"], "y": y,
                                   "w": b["l"], "h": b["w"], "rotated": b["rotated"]})
            y += b["w"]

    else:  # col
        x = 0.0
        for _ in range(a["count"]):
            for row in range(a["per_stripe"]):
                positions.append({"x": x, "y": row * a["w"],
                                   "w": a["l"], "h": a["w"], "rotated": a["rotated"]})
            x += a["l"]
        for _ in range(b["count"]):
            for row in range(b["per_stripe"]):
                positions.append({"x": x, "y": row * b["w"],
                                   "w": b["l"], "h": b["w"], "rotated": b["rotated"]})
            x += b["l"]

    return positions


def pod_dimensions(positions: List[Dict]) -> tuple:
    """Bounding box of all carton footprints (excludes pallet itself)."""
    if not positions:
        return 0.0, 0.0
    max_x = max(c["x"] + c["w"] for c in positions)
    max_y = max(c["y"] + c["h"] for c in positions)
    return round(max_x, 3), round(max_y, 3)


def arrangement_description(config: Optional[Dict], ti: int) -> str:
    if not config:
        return f"{ti} cases"
    a, b = config["a"], config["b"]
    has_a = a["count"] > 0 and a["per_stripe"] > 0
    has_b = b["count"] > 0 and b["per_stripe"] > 0
    if has_a and has_b:
        dir_a = "cols" if not a["rotated"] else "cols (rot.)"
        dir_b = "cols (rot.)" if not b["rotated"] else "cols"
        return (f"Mixed: {a['count']}×{a['per_stripe']} + "
                f"{b['count']}×{b['per_stripe']}")
    if has_a:
        return f"{'Rotated' if a['rotated'] else 'Uniform'}: {a['count']}×{a['per_stripe']}"
    if has_b:
        return f"{'Rotated' if b['rotated'] else 'Uniform'}: {b['count']}×{b['per_stripe']}"
    return "0 cases"


def calculate(
    case_l: float,
    case_w: float,
    case_h: float,
    max_height: float,
    pallet_l: float,
    pallet_w: float,
    pallet_h: float,
) -> dict:
    """
    Full pallet calculation.

    max_height is the maximum height of a single loaded pallet including the
    pallet board itself. Hi is always based on one pallet — stacking is a
    truckload-level concern handled outside this function.
    """
    case_l, case_w, case_h = _D(case_l), _D(case_w), _D(case_h)
    pallet_l, pallet_w, pallet_h, max_height = _D(pallet_l), _D(pallet_w), _D(pallet_h), _D(max_height)

    ti, config = find_optimal_arrangement(case_l, case_w, pallet_l, pallet_w)

    case_h_safe = max(case_h, _D('0.01'))
    available_h = max_height - pallet_h

    hi = max(0, int(available_h / case_h_safe))
    total = ti * hi
    pod_height = hi * case_h

    pallet_area = pallet_l * pallet_w
    case_footprint = case_l * case_w
    efficiency = (ti * case_footprint) / pallet_area if pallet_area > 0 else _D('0')

    positions = generate_positions(config) if config else []
    desc = arrangement_description(config, ti)
    p_len, p_wid = pod_dimensions(positions)

    return {
        "ti": ti,
        "hi": hi,
        "total": total,
        "case_h": round(float(case_h), 2),
        "pod_height": round(float(pod_height), 2),
        "efficiency": round(float(efficiency), 4),
        "pallet_length": float(pallet_l),
        "pallet_width": float(pallet_w),
        "pod_length": p_len,
        "pod_width": p_wid,
        "arrangement": positions,
        "arrangement_desc": desc,
        "available_height": round(float(available_h), 2),
    }
