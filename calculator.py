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
from typing import Dict, List, Optional, Tuple


def find_optimal_arrangement(
    carton_l: float,
    carton_w: float,
    pallet_l: float,
    pallet_w: float,
) -> Tuple[int, Optional[Dict]]:
    """
    Find maximum Ti and the arrangement config that achieves it.

    Tries all stripe patterns over both pallet dimensions with both carton
    orientations: n stripes of A + remaining space filled with B stripes.
    """
    if carton_l <= 0 or carton_w <= 0 or pallet_l <= 0 or pallet_w <= 0:
        return 0, None

    best_ti = 0
    best_config: Optional[Dict] = None

    # Natural orientation A = (carton_l × carton_w); B is 90° rotation.
    # We enumerate both choices of "primary" orientation so that all
    # combinations are covered without explicit A/B labelling confusion.
    for a_l, a_w in [(carton_l, carton_w), (carton_w, carton_l)]:
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
                    "row", pallet_l, pallet_w,
                    n_a, per_a, a_l, a_w,
                    n_b, per_b, b_l, b_w,
                    carton_l, carton_w,
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
                    "col", pallet_l, pallet_w,
                    n_a, per_a, a_l, a_w,
                    n_b, per_b, b_l, b_w,
                    carton_l, carton_w,
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
        return f"{ti} cartons"
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
    return "0 cartons"


def calculate(
    carton_l: float,
    carton_w: float,
    carton_h: float,
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
    ti, config = find_optimal_arrangement(carton_l, carton_w, pallet_l, pallet_w)

    carton_h_safe = max(carton_h, 0.01)
    available_h = max_height - pallet_h

    hi = max(0, int(available_h / carton_h_safe))
    total = ti * hi
    stack_height = hi * carton_h

    pallet_area = pallet_l * pallet_w
    carton_footprint = carton_l * carton_w
    efficiency = (ti * carton_footprint) / pallet_area if pallet_area > 0 else 0.0

    positions = generate_positions(config) if config else []
    desc = arrangement_description(config, ti)
    p_len, p_wid = pod_dimensions(positions)

    return {
        "ti": ti,
        "hi": hi,
        "total": total,
        "carton_h": round(carton_h, 2),
        "stack_height": round(stack_height, 2),
        "efficiency": round(efficiency, 4),
        "pallet_length": pallet_l,
        "pallet_width": pallet_w,
        "pod_length": p_len,
        "pod_width": p_wid,
        "arrangement": positions,
        "arrangement_desc": desc,
        "available_height": round(available_h, 2),
    }
