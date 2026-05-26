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
                    "row", pallet_l, pallet_w,
                    n_a, per_a, a_l, a_w,
                    n_b, per_b, b_l, b_w,
                    case_l, case_w,
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
                    case_l, case_w,
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


def place_ring(
    case_l: float,
    case_w: float,
    rect_l: float,
    rect_w: float,
    sides: List[str],
    rounding_gaps: bool,
) -> Optional[Dict]:
    sides_set = set(sides)

    fb_count = ("front" in sides_set) + ("back" in sides_set)
    lr_count = ("left" in sides_set) + ("right" in sides_set)
    inner_l = rect_l - case_l * fb_count  # front/back eat into L
    inner_w = rect_w - case_l * lr_count  # left/right eat into W

    if inner_l < -1e-9 or inner_w < -1e-9:
        return None

    left_right_span = rect_l  # left/right span L minus front/back depth
    if "front" in sides_set:
        left_right_span -= case_l
    if "back" in sides_set:
        left_right_span -= case_l

    counts: Dict[str, int] = {}

    for side in ("front", "back"):
        if side not in sides_set:
            continue
        n = int(rect_w / case_w)  # front/back span W (40" side)
        if n == 0:
            return None
        if not rounding_gaps and rect_w % case_w > 1e-9:
            return None
        counts[side] = n

    for side in ("left", "right"):
        if side not in sides_set:
            continue
        if left_right_span < case_w - 1e-9:
            return None
        n = int(left_right_span / case_w)
        if n == 0:
            return None
        if not rounding_gaps and left_right_span % case_w > 1e-9:
            return None
        counts[side] = n

    return {
        "counts": counts,
        "total": sum(counts.values()),
        "inner_l": max(0.0, inner_l),
        "inner_w": max(0.0, inner_w),
    }


def _place_partial_ring(
    case_l: float,
    case_w: float,
    rect_l: float,
    rect_w: float,
    sides: List[str],
    rounding_gaps: bool,
) -> int:
    """
    Place cases on whichever selected sides fit ≥1 case independently.
    Used when force_fill_on_failure=False and a full ring is no longer possible.
    Returns total cases placed across all feasible sides.
    """
    sides_set = set(sides)
    total = 0

    left_right_span = rect_l  # left/right span L minus front/back depth
    if "front" in sides_set:
        left_right_span -= case_l
    if "back" in sides_set:
        left_right_span -= case_l

    for side in ("front", "back"):
        if side not in sides_set:
            continue
        if rect_l < case_l - 1e-9:
            continue
        n = int(rect_w / case_w)  # front/back span W (40" side)
        if n > 0 and (rounding_gaps or rect_w % case_w < 1e-9):
            total += n

    if left_right_span >= case_w - 1e-9:
        for side in ("left", "right"):
            if side not in sides_set:
                continue
            n = int(left_right_span / case_w)
            if n > 0 and (rounding_gaps or left_right_span % case_w < 1e-9):
                total += n

    return total


def find_shoppable_arrangement(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
    sides: List[str],
    max_empty_pct: float = 0.15,
    rounding_gaps: bool = True,
    min_footprint: Tuple[float, float] = (37.0, 45.0),
    force_fill_on_failure: bool = True,
) -> Dict:
    """
    Place concentric rings then fill or leave chimney per configuration.

    Returns:
        ti           — total cases placed (rings + optional fill)
        mode         — 'pure_facing' | 'filled' | 'partial' | 'error'
        void_pct     — fraction of pallet area not covered by cases
        ring_count   — number of complete rings placed
        error        — human-readable message when mode == 'error', else None
    """
    pallet_area = pallet_l * pallet_w
    case_area = case_l * case_w
    rect_l, rect_w = pallet_l, pallet_w
    ring_ti = 0
    ring_count = 0

    while True:
        ring = place_ring(case_l, case_w, rect_l, rect_w, sides, rounding_gaps)
        if ring is None:
            break
        ring_ti += ring["total"]
        ring_count += 1
        rect_l = ring["inner_l"]
        rect_w = ring["inner_w"]

    if not force_fill_on_failure:
        partial_ti = _place_partial_ring(case_l, case_w, rect_l, rect_w, sides, rounding_gaps)
        total_ti = ring_ti + partial_ti
        void_pct = max(0.0, (pallet_area - total_ti * case_area) / pallet_area)
        return {
            "ti": total_ti,
            "mode": "partial",
            "void_pct": round(void_pct, 4),
            "ring_count": ring_count,
            "error": None,
        }

    if ring_count == 0:
        return {
            "ti": 0,
            "mode": "error",
            "void_pct": 1.0,
            "ring_count": 0,
            "error": "Case dimensions cannot form a shoppable ring on the selected sides.",
        }

    void_after_rings = max(0.0, (pallet_area - ring_ti * case_area) / pallet_area)

    if void_after_rings <= max_empty_pct:
        return {
            "ti": ring_ti,
            "mode": "pure_facing",
            "void_pct": round(void_after_rings, 4),
            "ring_count": ring_count,
            "error": None,
        }

    # Force-fill the interior
    fill_ti = 0
    min_dim = min(case_l, case_w)
    if rect_l >= min_dim - 1e-9 and rect_w >= min_dim - 1e-9:
        fill_ti, _ = find_optimal_arrangement(case_l, case_w, rect_l, rect_w)

    total_ti = ring_ti + fill_ti
    void_pct = max(0.0, (pallet_area - total_ti * case_area) / pallet_area)

    if void_pct <= max_empty_pct:
        mode = "filled"
        error_msg = None
    else:
        mode = "error"
        error_msg = (
            f"Void ({void_pct:.0%}) exceeds maximum allowed ({max_empty_pct:.0%}) "
            "even after filling the interior."
        )

    return {
        "ti": total_ti,
        "mode": mode,
        "void_pct": round(void_pct, 4),
        "ring_count": ring_count,
        "error": error_msg,
    }


def generate_ring_positions(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
    sides: List[str],
    max_empty_pct: float = 0.15,
    rounding_gaps: bool = True,
    force_fill_on_failure: bool = True,
) -> List[Dict]:
    """
    Return per-case positions for shoppable ring visualization.

    Each entry: {x, y, w, h, ring, side}
    ring=1,2,... for concentric rings; ring=0 for force-fill cases.
    side='front'|'back'|'left'|'right'|'fill'.

    Mirrors find_shoppable_arrangement() exactly so the diagram matches
    the reported Ti and mode.
    """
    sides_set = set(sides)
    positions: List[Dict] = []
    rect_l, rect_w = pallet_l, pallet_w
    ox, oy = 0.0, 0.0
    ring_ti = 0
    ring_num = 0
    case_area = case_l * case_w
    pallet_area = pallet_l * pallet_w

    while True:
        ring = place_ring(case_l, case_w, rect_l, rect_w, sides, rounding_gaps)
        if ring is None:
            break
        ring_num += 1
        y_offset = case_l if "front" in sides_set else 0.0
        left_right_span = rect_l
        if "front" in sides_set:
            left_right_span -= case_l
        if "back" in sides_set:
            left_right_span -= case_l

        # front/back span W (rect_w); pack from both ends so gap falls in the middle
        if "front" in sides_set:
            n = ring["counts"]["front"]
            gap = rect_w - n * case_w
            k = n // 2
            xs = ([ox + i * case_w for i in range(k)] +
                  [ox + k * case_w + gap + i * case_w for i in range(n - k)])
            for x in xs:
                positions.append({
                    "x": round(x, 6), "y": round(oy, 6),
                    "w": case_w, "h": case_l, "ring": ring_num, "side": "front",
                })
        if "back" in sides_set:
            n = ring["counts"]["back"]
            gap = rect_w - n * case_w
            k = n // 2
            xs = ([ox + i * case_w for i in range(k)] +
                  [ox + k * case_w + gap + i * case_w for i in range(n - k)])
            for x in xs:
                positions.append({
                    "x": round(x, 6),
                    "y": round(oy + rect_l - case_l, 6),
                    "w": case_w, "h": case_l, "ring": ring_num, "side": "back",
                })
        # left/right span L (left_right_span); pack from both ends so gap falls in the middle
        if "left" in sides_set:
            n = ring["counts"]["left"]
            gap = left_right_span - n * case_w
            k = n // 2
            ys = ([oy + y_offset + i * case_w for i in range(k)] +
                  [oy + y_offset + k * case_w + gap + i * case_w for i in range(n - k)])
            for y in ys:
                positions.append({
                    "x": round(ox, 6),
                    "y": round(y, 6),
                    "w": case_l, "h": case_w, "ring": ring_num, "side": "left",
                })
        if "right" in sides_set:
            n = ring["counts"]["right"]
            gap = left_right_span - n * case_w
            k = n // 2
            ys = ([oy + y_offset + i * case_w for i in range(k)] +
                  [oy + y_offset + k * case_w + gap + i * case_w for i in range(n - k)])
            for y in ys:
                positions.append({
                    "x": round(ox + rect_w - case_l, 6),
                    "y": round(y, 6),
                    "w": case_l, "h": case_w, "ring": ring_num, "side": "right",
                })

        ring_ti += ring["total"]
        if "left" in sides_set:
            ox += case_l
        if "front" in sides_set:
            oy += case_l
        rect_l = ring["inner_l"]
        rect_w = ring["inner_w"]

    # Add force-fill positions only when the algorithm would have filled
    if force_fill_on_failure and ring_num > 0:
        void_after_rings = max(0.0, (pallet_area - ring_ti * case_area) / pallet_area)
        min_dim = min(case_l, case_w)
        if (void_after_rings > max_empty_pct
                and rect_l >= min_dim - 1e-9
                and rect_w >= min_dim - 1e-9):
            _, fill_config = find_optimal_arrangement(case_l, case_w, rect_w, rect_l)
            if fill_config:
                for pos in generate_positions(fill_config):
                    positions.append({
                        "x": round(ox + pos["x"], 6),
                        "y": round(oy + pos["y"], 6),
                        "w": pos["w"], "h": pos["h"],
                        "ring": 0, "side": "fill",
                    })

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
    ti, config = find_optimal_arrangement(case_l, case_w, pallet_l, pallet_w)

    case_h_safe = max(case_h, 0.01)
    available_h = max_height - pallet_h

    hi = max(0, int(available_h / case_h_safe))
    total = ti * hi
    pod_height = hi * case_h

    pallet_area = pallet_l * pallet_w
    case_footprint = case_l * case_w
    efficiency = (ti * case_footprint) / pallet_area if pallet_area > 0 else 0.0

    positions = generate_positions(config) if config else []
    desc = arrangement_description(config, ti)
    p_len, p_wid = pod_dimensions(positions)

    return {
        "ti": ti,
        "hi": hi,
        "total": total,
        "case_h": round(case_h, 2),
        "pod_height": round(pod_height, 2),
        "efficiency": round(efficiency, 4),
        "pallet_length": pallet_l,
        "pallet_width": pallet_w,
        "pod_length": p_len,
        "pod_width": p_wid,
        "arrangement": positions,
        "arrangement_desc": desc,
        "available_height": round(available_h, 2),
    }
