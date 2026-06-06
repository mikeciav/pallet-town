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
    # case_l is the labeled face; strip depth = case_w so labeled face shows outward
    inner_l = rect_l - case_w * fb_count
    inner_w = rect_w - case_w * lr_count

    if inner_l < -1e-9 or inner_w < -1e-9:
        return None

    left_right_span = rect_l
    if "front" in sides_set:
        left_right_span -= case_w
    if "back" in sides_set:
        left_right_span -= case_w

    counts: Dict[str, int] = {}

    for side in ("front", "back"):
        if side not in sides_set:
            continue
        n = int(rect_w / case_l)  # labeled face spans W
        if n == 0:
            return None
        if not rounding_gaps and rect_w % case_l > 1e-9:
            return None
        counts[side] = n

    for side in ("left", "right"):
        if side not in sides_set:
            continue
        if left_right_span < case_l - 1e-9:
            return None
        n = int(left_right_span / case_l)  # labeled face spans L
        if n == 0:
            return None
        if not rounding_gaps and left_right_span % case_l > 1e-9:
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

    left_right_span = rect_l
    if "front" in sides_set:
        left_right_span -= case_w
    if "back" in sides_set:
        left_right_span -= case_w

    for side in ("front", "back"):
        if side not in sides_set:
            continue
        if rect_l < case_w - 1e-9:  # need case_w depth
            continue
        n = int(rect_w / case_l)  # labeled face spans W
        if n > 0 and (rounding_gaps or rect_w % case_l < 1e-9):
            total += n

    if left_right_span >= case_l - 1e-9:
        for side in ("left", "right"):
            if side not in sides_set:
                continue
            n = int(left_right_span / case_l)  # labeled face spans L
            if n > 0 and (rounding_gaps or left_right_span % case_l < 1e-9):
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
        # Cases too large for any shoppable ring: fall back to standard packing
        std_ti, _ = find_optimal_arrangement(case_l, case_w, pallet_l, pallet_w)
        void_pct = max(0.0, (pallet_area - std_ti * case_area) / pallet_area)
        return {
            "ti": std_ti,
            "mode": "standard",
            "void_pct": round(void_pct, 4),
            "ring_count": 0,
            "error": None,
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

    # Fill the interior to minimize void; always return the best result we can achieve
    fill_ti = 0
    min_dim = min(case_l, case_w)
    if rect_l >= min_dim - 1e-9 and rect_w >= min_dim - 1e-9:
        fill_ti, _ = find_optimal_arrangement(case_l, case_w, rect_l, rect_w)

    total_ti = ring_ti + fill_ti
    void_pct = max(0.0, (pallet_area - total_ti * case_area) / pallet_area)

    return {
        "ti": total_ti,
        "mode": "filled",
        "void_pct": round(void_pct, 4),
        "ring_count": ring_count,
        "error": None,
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
        # case_w is the strip depth; y_offset pushes left/right past the front strip
        y_offset = case_w if "front" in sides_set else 0.0
        left_right_span = rect_l
        if "front" in sides_set:
            left_right_span -= case_w
        if "back" in sides_set:
            left_right_span -= case_w

        # front/back: labeled face (case_l) spans W; case_w is depth into L
        if "front" in sides_set:
            n = ring["counts"]["front"]
            gap = rect_w - n * case_l
            k = n // 2
            xs = ([ox + i * case_l for i in range(k)] +
                  [ox + k * case_l + gap + i * case_l for i in range(n - k)])
            for x in xs:
                positions.append({
                    "x": round(x, 6), "y": round(oy, 6),
                    "w": case_l, "h": case_w, "ring": ring_num, "side": "front",
                })
        if "back" in sides_set:
            n = ring["counts"]["back"]
            gap = rect_w - n * case_l
            k = n // 2
            xs = ([ox + i * case_l for i in range(k)] +
                  [ox + k * case_l + gap + i * case_l for i in range(n - k)])
            for x in xs:
                positions.append({
                    "x": round(x, 6),
                    "y": round(oy + rect_l - case_w, 6),
                    "w": case_l, "h": case_w, "ring": ring_num, "side": "back",
                })
        # left/right: labeled face (case_l) spans L; case_w is depth into W
        if "left" in sides_set:
            n = ring["counts"]["left"]
            gap = left_right_span - n * case_l
            k = n // 2
            ys = ([oy + y_offset + i * case_l for i in range(k)] +
                  [oy + y_offset + k * case_l + gap + i * case_l for i in range(n - k)])
            for y in ys:
                positions.append({
                    "x": round(ox, 6),
                    "y": round(y, 6),
                    "w": case_w, "h": case_l, "ring": ring_num, "side": "left",
                })
        if "right" in sides_set:
            n = ring["counts"]["right"]
            gap = left_right_span - n * case_l
            k = n // 2
            ys = ([oy + y_offset + i * case_l for i in range(k)] +
                  [oy + y_offset + k * case_l + gap + i * case_l for i in range(n - k)])
            for y in ys:
                positions.append({
                    "x": round(ox + rect_w - case_w, 6),
                    "y": round(y, 6),
                    "w": case_w, "h": case_l, "ring": ring_num, "side": "right",
                })

        ring_ti += ring["total"]
        if "left" in sides_set:
            ox += case_w  # strip depth = case_w
        if "front" in sides_set:
            oy += case_w  # strip depth = case_w
        rect_l = ring["inner_l"]
        rect_w = ring["inner_w"]

    if force_fill_on_failure:
        if ring_num == 0:
            # No rings fit: fall back to standard arrangement.
            # Swap pallet_w/pallet_l so generate_positions x→W, y→L (matches shoppable axes).
            _, std_config = find_optimal_arrangement(case_l, case_w, pallet_w, pallet_l)
            for pos in generate_positions(std_config):
                positions.append({
                    "x": round(pos["x"], 6),
                    "y": round(pos["y"], 6),
                    "w": pos["w"], "h": pos["h"],
                    "ring": 0, "side": "fill",
                })
        else:
            # Fill the interior when rings leave too much void
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


def find_shoppable_v2(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
    sides: List[str],
) -> Dict:
    """
    Corner-spiral shoppable arrangement — counts TI from generated positions.
    """
    pallet_area = pallet_l * pallet_w
    case_area = case_l * case_w
    min_box = case_l + case_w

    if pallet_w < min_box - 1e-9 or pallet_l < min_box - 1e-9:
        std_ti, _ = find_optimal_arrangement(case_l, case_w, pallet_l, pallet_w)
        void_pct = max(0.0, (pallet_area - std_ti * case_area) / pallet_area)
        return {"ti": std_ti, "mode": "standard", "void_pct": round(void_pct, 4),
                "ring_count": 0, "error": None}

    positions = generate_shoppable_v2_positions(case_l, case_w, pallet_l, pallet_w, sides)
    total_ti = len(positions)
    ring_count = max((p["ring"] for p in positions if p["ring"] > 0), default=0)
    void_pct = max(0.0, (pallet_area - total_ti * case_area) / pallet_area)
    return {
        "ti": total_ti,
        "mode": "shoppable_spiral",
        "void_pct": round(void_pct, 4),
        "ring_count": ring_count,
        "error": None,
    }


def generate_shoppable_v2_positions(
    case_l: float,
    case_w: float,
    pallet_l: float,
    pallet_w: float,
    sides: List[str],
) -> List[Dict]:
    """
    Corner-spiral shoppable arrangement.

    Clockwise from front-left corner, 4 sides per loop:
      FRONT (→): n regular cases (case_w × case_l deep) + corner case (case_l × case_w deep)
      RIGHT  (↑): n regular cases (case_l × case_w)      + corner case (case_w × case_l deep)
      BACK   (←): n regular cases (case_w × case_l deep) + corner case (case_l × case_w deep)
      LEFT   (↓): n regular cases (case_l × case_w)      — no trailing corner

    Each regular case has its label face (case_l) perpendicular to the nearest wall.
    Corner cases bridge to the next side: case_l runs parallel, case_w is the depth.
    Bounding box shrinks by case_l after each full loop.

    Coordinates: x = W direction (0→pallet_w), y = L direction (0→pallet_l).
    """
    positions: List[Dict] = []

    # A ring requires case_l depth for the row + case_w for at least one regular case beside the corner.
    min_ring_span = case_l + case_w

    # The bounding box shrinks inward by case_l on each side after every completed ring.
    left_x   = 0.0
    bottom_y = 0.0
    right_x  = float(pallet_w)
    top_y    = float(pallet_l)
    ring = 1

    while True:
        ring_width  = right_x - left_x   # x-span available for this ring
        ring_height = top_y - bottom_y   # y-span available for this ring

        # Stop when the remaining rectangle is too small for a complete ring on either axis.
        if ring_width < min_ring_span - 1e-9 or ring_height < min_ring_span - 1e-9:
            break

        # ── FRONT side (travelling in the +x direction) ──────────────────────
        # Regular front cases stand case_l deep (into the pallet) and case_w wide (along the wall).
        # They pack from the left wall rightward, reserving space for one corner case at the end.
        num_front_cases = max(0, int((ring_width - case_l) / case_w))
        for i in range(num_front_cases):
            positions.append({
                "x": round(left_x + i * case_w, 6),
                "y": round(bottom_y, 6),
                "w": case_w, "h": case_l, "ring": ring, "side": "front",
            })

        # Front corner case: rotated 90° so its case_l dimension runs along the x-axis,
        # bridging the gap between the front row and the right column.
        front_corner_x = left_x + num_front_cases * case_w
        positions.append({
            "x": round(front_corner_x, 6),
            "y": round(bottom_y, 6),
            "w": case_l, "h": case_w, "ring": ring, "side": "front",
        })

        # ── RIGHT side (travelling in the +y direction) ──────────────────────
        # Regular right cases stand case_l deep (into the pallet) and case_w tall (along the wall).
        # The column starts above the front corner and leaves room for one corner case at the top.
        right_col_start_y = bottom_y + case_w  # front corner occupies case_w in y
        num_right_cases   = max(0, int((ring_height - case_w - case_l) / case_w))
        for i in range(num_right_cases):
            positions.append({
                "x": round(right_x - case_l, 6),
                "y": round(right_col_start_y + i * case_w, 6),
                "w": case_l, "h": case_w, "ring": ring, "side": "right",
            })

        # Right corner case: rotated so its case_l dimension runs along the y-axis,
        # bridging the gap between the right column and the back row.
        right_corner_y = right_col_start_y + num_right_cases * case_w
        positions.append({
            "x": round(right_x - case_w, 6),
            "y": round(right_corner_y, 6),
            "w": case_w, "h": case_l, "ring": ring, "side": "right",
        })

        # ── BACK side (travelling in the -x direction) ───────────────────────
        # Regular back cases stand case_l deep and case_w wide, packed right-to-left.
        # The row's right edge is the inner face of the right corner (right_x - case_w).
        back_row_right_x  = right_x - case_w
        num_back_cases    = max(0, int((back_row_right_x - left_x - case_l) / case_w))
        for i in range(num_back_cases):
            positions.append({
                "x": round(back_row_right_x - (i + 1) * case_w, 6),
                "y": round(top_y - case_l, 6),
                "w": case_w, "h": case_l, "ring": ring, "side": "back",
            })

        # Back corner case: rotated so its case_l dimension runs along the x-axis,
        # bridging the gap between the back row and the left column.
        back_corner_x = back_row_right_x - num_back_cases * case_w - case_l
        positions.append({
            "x": round(back_corner_x, 6),
            "y": round(top_y - case_w, 6),
            "w": case_l, "h": case_w, "ring": ring, "side": "back",
        })

        # ── LEFT side (travelling in the -y direction) ───────────────────────
        # Regular left cases stand case_l deep and case_w tall, packed top-to-bottom.
        # No trailing corner — the left side terminates where the next ring's front row begins.
        left_col_top_y = top_y - case_w  # back corner occupies case_w in y
        num_left_cases = max(0, int((left_col_top_y - (bottom_y + case_l)) / case_w))
        for i in range(num_left_cases):
            positions.append({
                "x": round(left_x, 6),
                "y": round(left_col_top_y - (i + 1) * case_w, 6),
                "w": case_l, "h": case_w, "ring": ring, "side": "left",
            })

        # Shrink the bounding box inward by case_l on all four sides for the next ring.
        ring += 1
        left_x   += case_l
        bottom_y += case_l
        right_x  -= case_l
        top_y    -= case_l

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
