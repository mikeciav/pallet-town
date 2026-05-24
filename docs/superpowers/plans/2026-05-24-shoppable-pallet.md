# Shoppable Pallet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a concentric-ring shoppable pallet calculator for club store retailers, surfacing both standard Ti and shoppable Ti with configurable void, footprint, and gap constraints.

**Architecture:** New `place_ring()` and `find_shoppable_arrangement()` functions in `calculator.py` do the ring math; `app.py`'s `/api/calculate` accepts an optional `shoppable` block (club stores only) and returns a `shoppable` object; `index.html` + `app.js` expand a Club Display Options panel when a club store is selected.

**Tech Stack:** Python 3 / Flask, vanilla JS, existing `pytest` test suite (`test_calculator.py`, `test_app.py`).

**Spec:** `docs/superpowers/specs/2026-05-24-shoppable-pallet-design.md`
**ADR:** `docs/adr/0001-shoppable-pallet-algorithm.md`

---

## File map

| File | Change |
|---|---|
| `calculator.py` | Add `place_ring()`, `_place_partial_ring()`, `find_shoppable_arrangement()` |
| `app.py` | Backfill new retailer fields; update `/api/calculate` to parse/validate/wire shoppable block |
| `retailers.json` | Add `is_club_store` / `chimney_allowed` to Sam's Club, Costco, BJ's Wholesale |
| `templates/index.html` | Add `#club-display-panel` HTML section and `#shoppable-results` HTML section |
| `static/js/app.js` | Show/hide panel, send shoppable params, render shoppable results |
| `test_calculator.py` | Add `TestPlaceRing` and `TestShoppableArrangement` classes |
| `test_app.py` | Add `TestShoppableAPI` class |

---

## Task 1: Retailer data model — backfill `is_club_store` and `chimney_allowed`

**Files:**
- Modify: `app.py` (`DEFAULT_RETAILERS`, `load_retailers()`, `_parse_retailer_body()`)
- Modify: `retailers.json`
- Test: `test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_app.py`:

```python
class TestRetailerClubFields:
    def test_club_stores_have_is_club_store_true(self, client):
        r = client.get('/api/retailers')
        retailers = r.get_json()
        for name in ("Sam's Club", "Costco", "BJ's Wholesale"):
            retailer = next(r for r in retailers if r['name'] == name)
            assert retailer['is_club_store'] is True, f"{name} should be is_club_store=True"
            assert retailer['chimney_allowed'] is False, f"{name} should be chimney_allowed=False"

    def test_non_club_stores_have_is_club_store_false(self, client):
        r = client.get('/api/retailers')
        retailers = r.get_json()
        amazon = next(r for r in retailers if r['name'] == 'Amazon')
        assert amazon['is_club_store'] is False
        assert amazon['chimney_allowed'] is False

    def test_load_retailers_backfills_missing_fields(self, tmp_path, monkeypatch):
        """Retailers saved before this feature was added get default values."""
        old_data = [{"id": 1, "name": "OldRetailer", "max_height": 60,
                     "double_stack_allowed": False, "max_pallets_per_floor": 26,
                     "no_pallet": False, "notes": ""}]
        rf = tmp_path / "retailers.json"
        rf.write_text(json.dumps(old_data))
        monkeypatch.setattr(flask_app, "RETAILERS_FILE", str(rf))
        r = client.get('/api/retailers')
        # Use load_retailers() directly since client fixture uses its own tmp_path
        import importlib
        importlib.reload(flask_app)  # not needed — just call load_retailers
        monkeypatch.setattr(flask_app, "RETAILERS_FILE", str(rf))
        data = flask_app.load_retailers()
        assert data[0]['is_club_store'] is False
        assert data[0]['chimney_allowed'] is False
```

Note: the `test_load_retailers_backfills_missing_fields` test calls `flask_app.load_retailers()` directly after pointing `RETAILERS_FILE` at the tmp file.

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest test_app.py::TestRetailerClubFields -v
```

Expected: `FAILED` — `KeyError: 'is_club_store'`

- [ ] **Step 3: Update `DEFAULT_RETAILERS` in `app.py`**

In `app.py`, update the three club stores in `DEFAULT_RETAILERS`. All others get `is_club_store: False, chimney_allowed: False`. Add fields to every entry to keep the list consistent:

```python
DEFAULT_RETAILERS = [
    {"id": 4,  "name": "Amazon",         "max_height": 50,   "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 13, "name": "Best Buy",       "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 15, "name": "BJ's Wholesale", "max_height": 60,   "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": True,  "chimney_allowed": False},
    {"id": 3,  "name": "Costco",         "max_height": 58.0, "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": True,  "chimney_allowed": False},
    {"id": 12, "name": "CVS",            "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 9,  "name": "Dollar General", "max_height": 57,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 10, "name": "Dollar Tree",    "max_height": 57,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 5,  "name": "Home Depot",     "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 7,  "name": "Kroger",         "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 6,  "name": "Lowe's",         "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 8,  "name": "Sam's Club",     "max_height": 60,   "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": True,  "chimney_allowed": False},
    {"id": 2,  "name": "Target",         "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 11, "name": "Walgreens",      "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 1,  "name": "Walmart",        "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 14, "name": "Whole Foods",    "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
]
```

- [ ] **Step 4: Update `load_retailers()` backfill in `app.py`**

In `load_retailers()`, add two more `setdefault` calls after the existing `r.setdefault("notes", "")`:

```python
def load_retailers():
    if os.path.exists(RETAILERS_FILE):
        with open(RETAILERS_FILE) as f:
            data = json.load(f)
        for r in data:
            r.setdefault("notes", "")
            r.setdefault("is_club_store", False)
            r.setdefault("chimney_allowed", False)
    else:
        data = [dict(r) for r in DEFAULT_RETAILERS]
    data.sort(key=lambda r: r["name"].casefold())
    return data
```

- [ ] **Step 5: Update `_parse_retailer_body()` in `app.py`**

```python
def _parse_retailer_body(data: dict, base=None) -> dict:
    base = base or {}
    return {
        "name":                  str(data.get("name", base.get("name", "Retailer"))),
        "max_height":            float(data.get("max_height", base.get("max_height", 60))),
        "double_stack_allowed":  bool(data.get("double_stack_allowed",
                                               base.get("double_stack_allowed", False))),
        "max_pallets_per_floor": int(data.get("max_pallets_per_floor",
                                              base.get("max_pallets_per_floor", 26))),
        "no_pallet":             bool(data.get("no_pallet", base.get("no_pallet", False))),
        "notes":                 str(data.get("notes", base.get("notes", ""))),
        "is_club_store":         bool(data.get("is_club_store", base.get("is_club_store", False))),
        "chimney_allowed":       bool(data.get("chimney_allowed", base.get("chimney_allowed", False))),
    }
```

- [ ] **Step 6: Update `retailers.json`**

Add `"is_club_store": true, "chimney_allowed": false` to Sam's Club (id 8), Costco (id 3), and BJ's Wholesale (id 15). Add `"is_club_store": false, "chimney_allowed": false` to all others.

Run this to verify the file is valid JSON after editing:

```bash
python3 -c "import json; json.load(open('retailers.json')); print('valid')"
```

- [ ] **Step 7: Run tests to confirm they pass**

```bash
python3 -m pytest test_app.py::TestRetailerClubFields -v
```

Expected: all 3 PASS.

- [ ] **Step 8: Commit**

```bash
git add app.py retailers.json test_app.py
git commit -m "feat: add is_club_store and chimney_allowed fields to retailer model"
```

---

## Task 2: `place_ring()` — core ring placement function

**Files:**
- Modify: `calculator.py`
- Test: `test_calculator.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_calculator.py`:

```python
from calculator import place_ring

class TestPlaceRing:
    ALL4 = ['front', 'back', 'left', 'right']

    def test_4sided_basic_counts(self):
        # pallet 48×40, case 10L×8W
        # front/back: floor(48/8)=6; left/right span=40-10-10=20, floor(20/8)=2
        ring = place_ring(10, 8, 48, 40, self.ALL4, rounding_gaps=True)
        assert ring is not None
        assert ring['counts']['front'] == 6
        assert ring['counts']['back']  == 6
        assert ring['counts']['left']  == 2
        assert ring['counts']['right'] == 2
        assert ring['total'] == 16

    def test_4sided_inner_rect(self):
        ring = place_ring(10, 8, 48, 40, self.ALL4, rounding_gaps=True)
        assert ring['inner_l'] == pytest.approx(28.0)
        assert ring['inner_w'] == pytest.approx(20.0)

    def test_ring2_fails_when_left_right_have_zero_cases(self):
        # inner rect 28×20: left/right span=20-20=0 → 0 cases → None
        ring = place_ring(10, 8, 28, 20, self.ALL4, rounding_gaps=True)
        assert ring is None

    def test_rounding_gaps_false_rejects_gap(self):
        # left/right span=20, 20%8=4 → gap → None when rounding_gaps=False
        ring = place_ring(10, 8, 48, 40, self.ALL4, rounding_gaps=False)
        assert ring is None

    def test_rounding_gaps_false_accepts_clean_division(self):
        # case 8×8: front/back 48%8=0 ✓; left/right span=40-16=24, 24%8=0 ✓
        ring = place_ring(8, 8, 48, 40, self.ALL4, rounding_gaps=False)
        assert ring is not None
        assert ring['counts']['front'] == 6
        assert ring['counts']['left']  == 3

    def test_3sided_front_left_right(self):
        # front: floor(48/8)=6; left/right span=40-10=30, floor(30/8)=3
        ring = place_ring(10, 8, 48, 40, ['front', 'left', 'right'], rounding_gaps=True)
        assert ring is not None
        assert ring['counts']['front'] == 6
        assert ring['counts']['left']  == 3
        assert ring['counts']['right'] == 3
        assert 'back' not in ring['counts']
        assert ring['inner_l'] == pytest.approx(38.0)  # 48-10
        assert ring['inner_w'] == pytest.approx(20.0)  # 40-10-10

    def test_2sided_front_back_only(self):
        # front/back: floor(48/8)=6; no left/right
        ring = place_ring(10, 8, 48, 40, ['front', 'back'], rounding_gaps=True)
        assert ring is not None
        assert ring['counts']['front'] == 6
        assert ring['counts']['back']  == 6
        assert 'left'  not in ring['counts']
        assert 'right' not in ring['counts']
        assert ring['inner_l'] == pytest.approx(48.0)  # L unchanged (no left/right)
        assert ring['inner_w'] == pytest.approx(20.0)  # W shrinks by 2×case_l

    def test_returns_none_when_inner_dims_negative(self):
        # rect 18×18, case 10: inner_l=18-20=-2 < 0 → None
        ring = place_ring(10, 8, 18, 18, self.ALL4, rounding_gaps=True)
        assert ring is None

    def test_returns_none_when_front_has_zero_cases(self):
        # rect 6×40, case 10: front floor(6/8)=0 → None
        ring = place_ring(10, 8, 6, 40, ['front', 'back'], rounding_gaps=True)
        assert ring is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest test_calculator.py::TestPlaceRing -v
```

Expected: `ERROR` — `ImportError: cannot import name 'place_ring'`

- [ ] **Step 3: Implement `place_ring()` in `calculator.py`**

Add after the existing `_make_config()` function:

```python
def place_ring(
    case_l: float,
    case_w: float,
    rect_l: float,
    rect_w: float,
    sides: List[str],
    rounding_gaps: bool,
) -> Optional[Dict]:
    """
    Attempt to place one concentric ring in the given rectangle.

    front/back strips span the full rect_l (long axis).
    left/right strips span the inner width between front/back strips.
    Corner ownership: front/back claim corners (full rect_l span).

    Returns a dict with case counts per side, total, and inner rectangle
    dimensions for the next ring. Returns None if any selected side yields
    0 cases or if rounding_gaps=False and a non-zero remainder exists.
    """
    sides_set = set(sides)

    # Compute inner rectangle dimensions after this ring is placed.
    # front/back consume depth in the W axis; left/right in the L axis.
    inner_l = rect_l - case_l * (("left" in sides_set) + ("right" in sides_set))
    inner_w = rect_w - case_l * (("front" in sides_set) + ("back" in sides_set))

    if inner_l < -1e-9 or inner_w < -1e-9:
        return None  # strips physically overlap — ring doesn't fit

    # Span available for left/right strips (between front/back strip edges)
    left_right_span = rect_w
    if "front" in sides_set:
        left_right_span -= case_l
    if "back" in sides_set:
        left_right_span -= case_l

    counts: Dict[str, int] = {}

    for side in ("front", "back"):
        if side not in sides_set:
            continue
        n = int(rect_l / case_w)
        if n == 0:
            return None
        if not rounding_gaps and rect_l % case_w > 1e-9:
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest test_calculator.py::TestPlaceRing -v
```

Expected: all 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add calculator.py test_calculator.py
git commit -m "feat: add place_ring() for shoppable pallet ring placement"
```

---

## Task 3: `find_shoppable_arrangement()` — concentric ring loop, fill, modes

**Files:**
- Modify: `calculator.py`
- Test: `test_calculator.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_calculator.py`:

```python
from calculator import find_shoppable_arrangement

class TestShoppableArrangement:
    ALL4 = ['front', 'back', 'left', 'right']

    def test_4sided_10x8_one_ring_then_fill(self):
        # Ring 1: 16 cases. Inner 28×20.
        # Ring 2 fails (left/right inner=0). Force fill 28×20.
        # find_optimal_arrangement(10,8,28,20): best is floor(28/8)*floor(20/10)=3*2=6
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4)
        assert result['ring_count'] == 1
        assert result['ti'] == 22          # 16 ring + 6 fill
        assert result['mode'] == 'filled'
        assert result['void_pct'] == pytest.approx((1920 - 22 * 80) / 1920, abs=1e-4)
        assert result['error'] is None

    def test_8x8_two_rings_pure_facing(self):
        # Ring 1 (48×40): front/back=6, left/right span=24, n=3 → 18 cases; inner 32×24
        # Ring 2 (32×24): front/back=4, left/right span=8, n=1 → 10 cases; inner 16×8
        # Ring 3 (16×8): inner_w=8-16=-8 <0 → None
        # Void before fill: (1920-28*64)/1920 = 128/1920 = 6.67% < 15% → pure_facing
        result = find_shoppable_arrangement(8, 8, 48, 40, self.ALL4)
        assert result['ring_count'] == 2
        assert result['mode'] == 'pure_facing'
        assert result['void_pct'] == pytest.approx(128 / 1920, abs=1e-4)

    def test_force_fill_brings_within_limit(self):
        # 10×8 4-sided: ring_ti=16, void=43% before fill, fill gives 6 more → 22 total
        # void after fill: (1920-22*80)/1920 = 160/1920 = 8.3% < 15% → filled, not error
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4, max_empty_pct=0.15)
        assert result['mode'] == 'filled'
        assert result['void_pct'] < 0.15

    def test_error_when_void_exceeds_limit_after_fill(self):
        # Very large cases: only 2 cases total possible; void ~= 92%
        result = find_shoppable_arrangement(20, 20, 48, 40, self.ALL4, max_empty_pct=0.10)
        assert result['mode'] == 'error'
        assert result['error'] is not None

    def test_partial_mode_when_force_fill_off(self):
        result = find_shoppable_arrangement(
            10, 8, 48, 40, self.ALL4,
            force_fill_on_failure=False
        )
        assert result['mode'] == 'partial'
        assert result['ring_count'] == 1

    def test_3sided_front_left_right(self):
        result = find_shoppable_arrangement(10, 8, 48, 40, ['front', 'left', 'right'])
        assert result['ring_count'] >= 1
        assert result['ti'] > 0
        assert result['mode'] in ('pure_facing', 'filled', 'partial')

    def test_rounding_gaps_false_zero_rings_then_error(self):
        # 10×8 on 48×40: left/right span=20, 20%8=4 → gap → 0 rings
        result = find_shoppable_arrangement(
            10, 8, 48, 40, self.ALL4, rounding_gaps=False
        )
        assert result['ring_count'] == 0
        assert result['mode'] == 'error'

    def test_ti_never_exceeds_standard_ti(self):
        ti_standard, _ = find_optimal_arrangement(10, 8, 48, 40)
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4)
        assert result['ti'] <= ti_standard

    def test_void_pct_in_0_to_1_range(self):
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4)
        assert 0.0 <= result['void_pct'] <= 1.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest test_calculator.py::TestShoppableArrangement -v
```

Expected: `ERROR` — `ImportError: cannot import name 'find_shoppable_arrangement'`

- [ ] **Step 3: Implement `_place_partial_ring()` helper in `calculator.py`**

Add after `place_ring()`:

```python
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

    left_right_span = rect_w
    if "front" in sides_set:
        left_right_span -= case_l
    if "back" in sides_set:
        left_right_span -= case_l

    for side in ("front", "back"):
        if side not in sides_set:
            continue
        if rect_w < case_l - 1e-9:
            continue
        n = int(rect_l / case_w)
        if n > 0 and (rounding_gaps or rect_l % case_w < 1e-9):
            total += n

    if left_right_span >= case_w - 1e-9:
        for side in ("left", "right"):
            if side not in sides_set:
                continue
            n = int(left_right_span / case_w)
            if n > 0 and (rounding_gaps or left_right_span % case_w < 1e-9):
                total += n

    return total
```

- [ ] **Step 4: Implement `find_shoppable_arrangement()` in `calculator.py`**

Add after `_place_partial_ring()`:

```python
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
    if rect_l >= case_w - 1e-9 and rect_w >= case_w - 1e-9:
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
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python3 -m pytest test_calculator.py::TestShoppableArrangement -v
```

Expected: all 9 PASS.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
python3 -m pytest test_calculator.py -v
```

Expected: all existing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add calculator.py test_calculator.py
git commit -m "feat: add find_shoppable_arrangement() with concentric ring algorithm"
```

---

## Task 4: API — validate the `shoppable` request block

**Files:**
- Modify: `app.py`
- Test: `test_app.py`

- [ ] **Step 1: Write the failing tests**

Add to `test_app.py`:

```python
SAMS_ID = "8"   # Sam's Club — is_club_store=True
AMAZON_ID = "4" # Amazon — is_club_store=False
VALID_DIMS = {"length": 10, "width": 8, "height": 6, "retailer_id": SAMS_ID}

class TestShoppableAPI:
    def test_shoppable_rejected_for_non_club_store(self, client):
        body = {**VALID_DIMS, "retailer_id": AMAZON_ID,
                "shoppable": {"sides": ["front", "back"]}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400
        assert 'club store' in r.get_json()['error'].lower()

    def test_shoppable_rejected_for_custom_retailer(self, client):
        body = {"length": 10, "width": 8, "height": 6,
                "retailer_id": "custom",
                "max_height": 60, "double_stack_allowed": False,
                "max_pallets_per_floor": 26, "no_pallet": False,
                "shoppable": {"sides": ["front"]}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400

    def test_shoppable_rejected_with_empty_sides(self, client):
        body = {**VALID_DIMS, "shoppable": {"sides": []}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400
        assert 'sides' in r.get_json()['error'].lower()

    def test_shoppable_rejected_with_invalid_side_name(self, client):
        body = {**VALID_DIMS, "shoppable": {"sides": ["front", "diagonal"]}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400

    def test_shoppable_rejected_when_chimney_not_allowed_and_fill_off(self, client):
        # Sam's Club has chimney_allowed=False; sending force_fill_on_failure=False is invalid
        body = {**VALID_DIMS,
                "shoppable": {"sides": ["front"], "force_fill_on_failure": False}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400
        assert 'chimney' in r.get_json()['error'].lower()

    def test_shoppable_accepted_for_club_store(self, client):
        body = {**VALID_DIMS, "shoppable": {"sides": ["front", "left", "right"]}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert 'shoppable' in data
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest test_app.py::TestShoppableAPI -v
```

Expected: `FAILED` — 200s where 400s are expected (shoppable block currently ignored).

- [ ] **Step 3: Add `_parse_shoppable_block()` helper to `app.py`**

Add this function just before `api_calculate()`:

```python
VALID_SIDES = {"front", "back", "left", "right"}

def _parse_shoppable_block(data: dict, retailer: dict):
    """
    Parse and validate the 'shoppable' key from an /api/calculate request body.

    Returns (params_dict, error_str). If error_str is not None the request
    should be rejected with 400.
    """
    shoppable = data.get("shoppable")
    if shoppable is None:
        return None, None  # not a shoppable request — fine

    if not retailer.get("is_club_store", False):
        return None, "shoppable display calculations are only available for club store retailers"

    sides = shoppable.get("sides")
    if not sides or not isinstance(sides, list) or len(sides) == 0:
        return None, "shoppable.sides must be a non-empty list"
    invalid = [s for s in sides if s not in VALID_SIDES]
    if invalid:
        return None, f"shoppable.sides contains invalid values: {invalid}"

    force_fill = bool(shoppable.get("force_fill_on_failure", True))
    if not force_fill and not retailer.get("chimney_allowed", False):
        return None, (
            f"{retailer.get('name', 'This retailer')} does not permit open chimneys; "
            "force_fill_on_failure must be true"
        )

    try:
        max_empty_pct = float(shoppable.get("max_empty_pct", 0.15))
        rounding_gaps = bool(shoppable.get("rounding_gaps", True))
        raw_fp = shoppable.get("min_footprint", [37.0, 45.0])
        min_footprint = (float(raw_fp[0]), float(raw_fp[1]))
    except (TypeError, ValueError, IndexError):
        return None, "invalid shoppable parameter values"

    return {
        "sides": sides,
        "max_empty_pct": max_empty_pct,
        "rounding_gaps": rounding_gaps,
        "min_footprint": min_footprint,
        "force_fill_on_failure": force_fill,
    }, None
```

- [ ] **Step 4: Call `_parse_shoppable_block()` in `api_calculate()`**

In `app.py`, update `api_calculate()` to call the new helper after the retailer is resolved. Replace the return line with:

```python
@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(force=True) or {}
    try:
        case_l = float(data["length"])
        case_w = float(data["width"])
        case_h = float(data["height"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "length, width, height are required numbers"}), 400

    if case_l <= 0 or case_w <= 0 or case_h <= 0:
        return jsonify({"error": "Dimensions must be positive"}), 400

    retailer_id = str(data.get("retailer_id", ""))
    if retailer_id == "custom":
        try:
            retailer = {
                "max_height":            float(data.get("max_height", 60)),
                "double_stack_allowed":  bool(data.get("double_stack_allowed", False)),
                "max_pallets_per_floor": int(data.get("max_pallets_per_floor", 26)),
                "no_pallet":             bool(data.get("no_pallet", False)),
                "is_club_store":         False,
                "chimney_allowed":       False,
            }
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid custom retailer params"}), 400
    else:
        retailer = next((r for r in load_retailers() if str(r["id"]) == retailer_id), None)
        if not retailer:
            return jsonify({"error": "Retailer not found"}), 404

    shoppable_params, shoppable_error = _parse_shoppable_block(data, retailer)
    if shoppable_error:
        return jsonify({"error": shoppable_error}), 400

    case_pack_qty = max(1, int(data.get("case_pack_qty", 1)))
    result = calculate(
        case_l=case_l,
        case_w=case_w,
        case_h=case_h,
        max_height=retailer["max_height"],
        pallet_l=PALLET_L,
        pallet_w=PALLET_W,
        pallet_h=0.0 if retailer.get("no_pallet", False) else PALLET_H,
    )
    stack_mult = 2 if retailer["double_stack_allowed"] else 1
    result["truckload_qty"] = (
        case_pack_qty * result["total"] * retailer["max_pallets_per_floor"] * stack_mult
    )
    result["case_pack_qty"]        = case_pack_qty
    result["max_pallets_per_floor"] = retailer["max_pallets_per_floor"]
    result["stack_multiplier"]      = stack_mult
    return jsonify(result)
```

(The shoppable result wiring is added in Task 5.)

- [ ] **Step 5: Run validation tests to confirm they pass**

```bash
python3 -m pytest test_app.py::TestShoppableAPI -v
```

Expected: the 5 validation tests (rejected_for_non_club, custom, empty_sides, invalid_side, chimney) PASS. The `test_shoppable_accepted_for_club_store` test may still FAIL because the response doesn't include a `shoppable` key yet — that's Task 5.

- [ ] **Step 6: Commit**

```bash
git add app.py test_app.py
git commit -m "feat: validate shoppable block in /api/calculate — club stores only"
```

---

## Task 5: API — wire shoppable result into response

**Files:**
- Modify: `app.py`
- Modify: `calculator.py` import line in `app.py`
- Test: `test_app.py`

- [ ] **Step 1: Write the failing test**

The `test_shoppable_accepted_for_club_store` test from Task 4 already covers this. Add more specific assertions to `test_app.py`:

```python
    def test_shoppable_response_shape(self, client):
        body = {**VALID_DIMS,
                "shoppable": {"sides": ["front", "left", "right"],
                              "max_empty_pct": 0.15,
                              "rounding_gaps": True}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 200
        d = r.get_json()
        assert 'total' in d         # standard Ti unaffected
        s = d['shoppable']
        assert isinstance(s['ti'], int)
        assert s['mode'] in ('pure_facing', 'filled', 'partial', 'error')
        assert 0.0 <= s['void_pct'] <= 1.0
        assert isinstance(s['ring_count'], int) and s['ring_count'] >= 0
        assert 'error' in s         # key present even when None

    def test_shoppable_ti_lte_standard_ti(self, client):
        body = {**VALID_DIMS,
                "shoppable": {"sides": ["front", "back", "left", "right"]}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        d = r.get_json()
        assert d['shoppable']['ti'] <= d['total']

    def test_no_shoppable_key_without_block(self, client):
        body = {**VALID_DIMS}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 200
        assert 'shoppable' not in r.get_json()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest test_app.py::TestShoppableAPI::test_shoppable_response_shape test_app.py::TestShoppableAPI::test_shoppable_ti_lte_standard_ti -v
```

Expected: `FAILED` — `shoppable` key missing from response.

- [ ] **Step 3: Update `app.py` import and wire result**

Update the import at the top of `app.py`:

```python
from calculator import calculate, find_shoppable_arrangement
```

Then in `api_calculate()`, add the shoppable call just before `return jsonify(result)`:

```python
    if shoppable_params is not None:
        shoppable_result = find_shoppable_arrangement(
            case_l=case_l,
            case_w=case_w,
            pallet_l=PALLET_L,
            pallet_w=PALLET_W,
            sides=shoppable_params["sides"],
            max_empty_pct=shoppable_params["max_empty_pct"],
            rounding_gaps=shoppable_params["rounding_gaps"],
            min_footprint=shoppable_params["min_footprint"],
            force_fill_on_failure=shoppable_params["force_fill_on_failure"],
        )
        result["shoppable"] = shoppable_result

    return jsonify(result)
```

- [ ] **Step 4: Run all shoppable API tests**

```bash
python3 -m pytest test_app.py::TestShoppableAPI -v
```

Expected: all 8 PASS.

- [ ] **Step 5: Run full test suite**

```bash
python3 -m pytest test_app.py -v
```

Expected: all existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py test_app.py
git commit -m "feat: wire find_shoppable_arrangement into /api/calculate response"
```

---

## Task 6: UI — Club Display Options HTML panel

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Add the Club Display Options panel HTML**

In `templates/index.html`, locate the `<div class="divider"></div>` that appears just before the `<button class="pt-btn" id="calc-btn">` element (the calculate button). Insert the following block immediately before that divider:

```html
          <!-- Club Display Options (visible only for club store retailers) -->
          <div id="club-display-panel" style="display:none">
            <div class="divider"></div>
            <div class="panel-header">
              <span class="panel-label">CLUB DISPLAY OPTIONS</span>
            </div>

            <div class="field-group" style="margin-top:4px">
              <label class="field-label">SHOPPABLE SIDES</label>
              <div id="side-selector" style="display:flex;gap:6px;margin-top:4px">
                <button class="side-btn active" data-side="front">FRONT</button>
                <button class="side-btn active" data-side="back">BACK</button>
                <button class="side-btn active" data-side="left">LEFT</button>
                <button class="side-btn active" data-side="right">RIGHT</button>
              </div>
              <div id="side-error" style="display:none;color:#ef4444;font-size:10px;margin-top:4px;font-family:monospace">
                At least 1 side must be selected.
              </div>
            </div>

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
              <div class="field-group">
                <label class="field-label">MAX EMPTY %</label>
                <div class="field-wrap">
                  <input type="number" id="club-max-empty" class="dim-input" value="15" min="0" max="100" step="1">
                  <span class="field-unit">%</span>
                </div>
              </div>
              <div class="field-group">
                <label class="field-label">MIN FOOTPRINT W</label>
                <div class="field-wrap">
                  <input type="number" id="club-fp-w" class="dim-input" value="37" min="0" step="0.5">
                  <span class="field-unit">in</span>
                </div>
              </div>
            </div>

            <div class="field-group" style="margin-top:8px">
              <label class="field-label">MIN FOOTPRINT L</label>
              <div class="field-wrap">
                <input type="number" id="club-fp-l" class="dim-input" value="45" min="0" step="0.5">
                <span class="field-unit">in</span>
              </div>
            </div>

            <div class="ie-row" style="margin-top:8px">
              <label class="toggle-label">
                <input type="checkbox" id="club-rounding-gaps" class="toggle-input" checked>
                <span class="toggle-track"><span class="toggle-thumb"></span></span>
                <span class="toggle-text">Allow Rounding Gaps</span>
              </label>
            </div>

            <div class="ie-row" style="margin-top:8px">
              <label class="toggle-label" id="club-fill-label">
                <input type="checkbox" id="club-fill-chimney" class="toggle-input" checked>
                <span class="toggle-track"><span class="toggle-thumb"></span></span>
                <span class="toggle-text">Fill Chimney</span>
              </label>
            </div>
          </div>
```

- [ ] **Step 2: Add the shoppable results section HTML**

In `templates/index.html`, locate `<div class="metrics-row">`. Just above it, add the error banner:

```html
          <!-- Shoppable error banner (hidden until error mode) -->
          <div id="shoppable-error-banner" style="display:none;background:#1c0a00;border:1px solid #7f1d1d;border-radius:6px;padding:8px 12px;margin-bottom:8px;font-family:monospace;font-size:11px;color:#f87171"></div>
```

Then find the closing `</div>` of `<div class="metrics-row">` (after the last metric card) and add the shoppable metrics row just after it:

```html
          <!-- Shoppable results row (hidden until a shoppable calc is run) -->
          <div id="shoppable-metrics-row" class="metrics-row" style="display:none;margin-top:4px;border-top:1px solid #1e2a45;padding-top:8px">
            <div class="metric-card" id="mc-shoppable-ti">
              <div class="metric-label">Shoppable Ti</div>
              <div class="metric-val" id="val-shoppable-ti">—</div>
              <div class="metric-sub">CASES / LAYER</div>
            </div>
            <div class="metric-card" id="mc-shoppable-void">
              <div class="metric-label">Void</div>
              <div class="metric-val" id="val-shoppable-void">—</div>
              <div class="metric-sub">EMPTY SPACE</div>
            </div>
            <div class="metric-card" id="mc-shoppable-rings">
              <div class="metric-label">Rings</div>
              <div class="metric-val" id="val-shoppable-rings">—</div>
              <div class="metric-sub">CONCENTRIC</div>
            </div>
            <div class="metric-card" id="mc-shoppable-mode">
              <div class="metric-label">Mode</div>
              <div class="metric-val" id="val-shoppable-mode" style="font-size:12px">—</div>
              <div class="metric-sub">DISPLAY TYPE</div>
            </div>
          </div>
```

- [ ] **Step 3: Add CSS for `.side-btn` to `static/css/style.css`**

Find an appropriate location in `style.css` (near other button styles) and add:

```css
.side-btn {
  background: #1a2235;
  border: 1px solid #374151;
  border-radius: 4px;
  color: #6b7280;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 4px 8px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.side-btn.active {
  background: #1e1535;
  border-color: #7c3aed;
  color: #c4b5fd;
}
.side-btn:hover:not(.active) {
  border-color: #4b5563;
  color: #9ca3af;
}
.toggle-label--disabled {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}
```

- [ ] **Step 4: Start dev server and verify static appearance**

```bash
python3 app.py
```

Open the calculator, select Sam's Club, and confirm the Club Display Options panel is still hidden (JS hasn't been added yet — that's Task 7). Verify the HTML structure is present in DevTools.

- [ ] **Step 5: Commit**

```bash
git add templates/index.html static/css/style.css
git commit -m "feat: add Club Display Options and shoppable results HTML"
```

---

## Task 7: UI — JS for club panel, request params, and results rendering

**Files:**
- Modify: `static/js/app.js`

- [ ] **Step 1: Add `updateClubPanel()` — show/hide panel on retailer change**

In `app.js`, find `function updateInfoBar()` and add the following function just after it:

```javascript
function updateClubPanel() {
  const rid = document.getElementById('retailer-select').value;
  const r = rid === 'custom' ? null : retailerById(rid);
  const isClub = r && r.is_club_store;
  document.getElementById('club-display-panel').style.display = isClub ? '' : 'none';
  if (!isClub) {
    // Hide shoppable results when switching away from a club store
    document.getElementById('shoppable-metrics-row').style.display = 'none';
    document.getElementById('shoppable-error-banner').style.display = 'none';
  }

  // Manage Fill Chimney toggle based on chimney_allowed
  const fillInput  = document.getElementById('club-fill-chimney');
  const fillLabel  = document.getElementById('club-fill-label');
  if (isClub && r && !r.chimney_allowed) {
    fillInput.checked = true;
    fillInput.disabled = true;
    fillLabel.classList.add('toggle-label--disabled');
    fillLabel.title = `${r.name} does not permit open chimneys`;
  } else {
    fillInput.disabled = false;
    fillLabel.classList.remove('toggle-label--disabled');
    fillLabel.title = '';
  }

  // Pre-populate sides based on retailer conventions
  if (isClub && r) {
    const DEFAULTS = {
      "Sam's Club": ['front', 'left', 'right'],
      "Costco":     ['front', 'left', 'right'],
      "BJ's Wholesale": ['front', 'back'],
    };
    const defaultSides = DEFAULTS[r.name] || ['front', 'left', 'right'];
    document.querySelectorAll('#side-selector .side-btn').forEach(btn => {
      const active = defaultSides.includes(btn.dataset.side);
      btn.classList.toggle('active', active);
    });
  }
}
```

- [ ] **Step 2: Wire `updateClubPanel()` into retailer change event**

In `setupCalculator()`, find this existing line:

```javascript
document.getElementById('retailer-select').addEventListener('change', updateInfoBar);
```

Replace it with:

```javascript
document.getElementById('retailer-select').addEventListener('change', () => {
  updateInfoBar();
  updateClubPanel();
});
```

Also call `updateClubPanel()` at the end of `setupCalculator()` (after `loadRetailers()` resolves — see Step 4).

- [ ] **Step 3: Add side-button toggle logic**

Add this function near `updateClubPanel()`:

```javascript
function setupSideSelector() {
  document.querySelectorAll('#side-selector .side-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const active = [...document.querySelectorAll('#side-selector .side-btn.active')];
      const willDeactivate = btn.classList.contains('active');
      if (willDeactivate && active.length <= 1) {
        document.getElementById('side-error').style.display = '';
        setTimeout(() => { document.getElementById('side-error').style.display = 'none'; }, 2000);
        return;
      }
      btn.classList.toggle('active');
    });
  });
}
```

Call `setupSideSelector()` at the bottom of `setupCalculator()`.

- [ ] **Step 4: Call `updateClubPanel()` after retailers load**

Find `async function loadRetailers()` and add a call to `updateClubPanel()` at the end of the `try` block, after `renderRetailersGrid()`:

```javascript
async function loadRetailers() {
  try {
    const res = await fetch(API.retailers);
    retailers = await res.json();
    syncRetailerSelects();
    renderRetailersGrid();
    updateClubPanel();   // ← add this line
  } catch {
    setStatus('Could not load retailers.', true);
  }
}
```

- [ ] **Step 5: Add `getShoppableParams()` — read club panel values**

Add this function near `updateClubPanel()`:

```javascript
function getShoppableParams() {
  const panel = document.getElementById('club-display-panel');
  if (!panel || panel.style.display === 'none') return null;

  const sides = [...document.querySelectorAll('#side-selector .side-btn.active')]
    .map(btn => btn.dataset.side);
  if (sides.length === 0) return null;

  return {
    sides,
    max_empty_pct: (parseFloat(document.getElementById('club-max-empty').value) || 15) / 100,
    rounding_gaps: document.getElementById('club-rounding-gaps').checked,
    min_footprint: [
      parseFloat(document.getElementById('club-fp-w').value) || 37,
      parseFloat(document.getElementById('club-fp-l').value) || 45,
    ],
    force_fill_on_failure: document.getElementById('club-fill-chimney').checked,
  };
}
```

- [ ] **Step 6: Include shoppable params in `doCalculate()`**

In `doCalculate()`, find this line:

```javascript
const body = { length: l, width: w, height: h, retailer_id: rid, case_pack_qty: cp };
```

Replace it with:

```javascript
const body = { length: l, width: w, height: h, retailer_id: rid, case_pack_qty: cp };
const shoppable = getShoppableParams();
if (shoppable) body.shoppable = shoppable;
```

- [ ] **Step 7: Add `renderShoppableResults()` — display shoppable metrics**

Add this function near `renderResults()`:

```javascript
function renderShoppableResults(s) {
  const banner = document.getElementById('shoppable-error-banner');
  const row    = document.getElementById('shoppable-metrics-row');

  if (!s) {
    banner.style.display = 'none';
    row.style.display = 'none';
    return;
  }

  if (s.mode === 'error') {
    banner.textContent = s.error || 'Shoppable constraints cannot be met.';
    banner.style.display = '';
  } else {
    banner.style.display = 'none';
  }

  const MODE_LABELS = {
    pure_facing: 'PURE FACING',
    filled:      'FILLED',
    partial:     'PARTIAL',
    error:       'ERROR',
  };
  const MODE_COLORS = {
    pure_facing: '#4ade80',
    filled:      '#7dd3fc',
    partial:     '#fb923c',
    error:       '#ef4444',
  };

  document.getElementById('val-shoppable-ti').textContent = s.ti;
  document.getElementById('val-shoppable-void').textContent = pct(s.void_pct);
  document.getElementById('val-shoppable-rings').textContent = s.ring_count;

  const modeEl = document.getElementById('val-shoppable-mode');
  modeEl.textContent = MODE_LABELS[s.mode] || s.mode;
  modeEl.style.color = MODE_COLORS[s.mode] || '#9ca3af';

  row.style.display = '';
}
```

- [ ] **Step 8: Call `renderShoppableResults()` from `renderResults()`**

At the end of `renderResults(d)`, add:

```javascript
  renderShoppableResults(d.shoppable || null);
```

- [ ] **Step 9: Test in browser**

Start the server and verify the full flow:

```bash
python3 app.py
```

1. Select **Amazon** → Club Display Options panel is hidden.
2. Select **Sam's Club** → panel appears with Front/Left/Right pre-selected, Fill Chimney toggle disabled with tooltip.
3. Select **BJ's Wholesale** → panel appears with Front/Back pre-selected.
4. Select **Costco**, enter dimensions (e.g. L=10, W=8, H=6), click CALCULATE → shoppable results row appears below standard metrics, showing Ti, Void %, Rings, and Mode.
5. Set Max Empty % to 1 and recalculate → mode should show ERROR and error banner appears.
6. Toggle off all but one side (confirm cannot deactivate the last one — error flash appears).

- [ ] **Step 10: Commit**

```bash
git add static/js/app.js
git commit -m "feat: Club Display Options panel JS — show/hide, side selector, shoppable results"
```

---

## Self-review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `is_club_store` + `chimney_allowed` on retailers | Task 1 |
| Concentric ring algorithm | Tasks 2–3 |
| `rounding_gaps`, `max_empty_pct`, `force_fill_on_failure`, `min_footprint` params | Tasks 2–3 |
| Hard rule: every selected side ≥1 case | Task 2 (`place_ring` returns None on 0-case side) |
| `pure_facing` / `filled` / `partial` / `error` modes | Task 3 |
| 400 for non-club-store + shoppable block | Task 4 |
| 400 for `force_fill_on_failure=False` when `chimney_allowed=False` | Task 4 |
| `total` unchanged, `shoppable` nested in response | Task 5 |
| Club Display Options panel (sides, max_empty_pct, min_footprint, rounding_gaps, fill chimney) | Tasks 6–7 |
| Side selector: min 1 selected | Task 7 step 3 |
| Fill Chimney disabled + tooltip when `chimney_allowed=False` | Task 7 step 1 |
| Shoppable Ti / void / ring count / mode in results | Task 7 step 7 |
| Error banner on `error` mode, shoppable Ti = 0 | Task 7 step 7 |
| Bulk import excluded | No task (nothing to do) |

**All spec requirements are covered.**
