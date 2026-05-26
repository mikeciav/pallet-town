"""
Unit tests for the pallet calculator.

Run with:  python3 -m pytest test_calculator.py -v
"""

import pytest
from calculator import calculate, find_optimal_arrangement, pod_dimensions, generate_positions
from calculator import place_ring
from calculator import find_shoppable_arrangement
from calculator import generate_ring_positions

# Standard pallet constants used in app.py
PL, PW, PH = 48.0, 40.0, 5.5


# ── Ti (cartons per layer) ────────────────────────────────────

class TestTi:
    def test_perfect_mixed_12x8(self):
        # 2 strips of 4 (12×8) + 2 strips of 6 (8×12) = 20 — 100% floor coverage
        ti, _ = find_optimal_arrangement(12, 8, PL, PW)
        assert ti == 20

    def test_square_carton_10x10(self):
        # Rotation irrelevant; 4×4 grid
        ti, _ = find_optimal_arrangement(10, 10, PL, PW)
        assert ti == 16

    def test_mixed_beats_uniform_14x6(self):
        # Uniform A: floor(48/14)×floor(40/6)=3×6=18
        # Uniform B: floor(48/6)×floor(40/14)=8×2=16
        # Mixed:     2 strips of 3 (14×6) + 2 strips of 8 (6×14) = 22
        ti, _ = find_optimal_arrangement(14, 6, PL, PW)
        assert ti == 22

    def test_column_split_7x5(self):
        # Col split: 6 cols×8 (7×5) + 1 col×5 (5×7) = 53
        ti, _ = find_optimal_arrangement(7, 5, PL, PW)
        assert ti == 53

    def test_cube_carton_8x8(self):
        # 6 cols × 5 rows = 30 (fits 48/8=6, 40/8=5)
        ti, _ = find_optimal_arrangement(8, 8, PL, PW)
        assert ti == 30

    def test_small_carton_6x6(self):
        # 8 cols × 6 rows = 48 (48/6=8, 40/6=6 with 4" gap)
        ti, _ = find_optimal_arrangement(6, 6, PL, PW)
        assert ti == 48

    def test_large_carton_16x12(self):
        # Mixed: 2 strips of 3 (16×12) + 1 strip of 4 (12×16) = 10
        ti, _ = find_optimal_arrangement(16, 12, PL, PW)
        assert ti == 10

    def test_very_large_carton_20x16(self):
        # Best: floor(48/20)×floor(40/16)=2×2=4, or floor(48/16)×floor(40/20)=3×2=6
        ti, _ = find_optimal_arrangement(20, 16, PL, PW)
        assert ti == 6

    def test_awkward_dims_11x9(self):
        # Mixed: 2 strips of 4 (11×9) + 2 strips of 5 (9×11) = 18
        ti, _ = find_optimal_arrangement(11, 9, PL, PW)
        assert ti == 18

    def test_carton_exactly_pallet_size(self):
        ti, _ = find_optimal_arrangement(PL, PW, PL, PW)
        assert ti == 1

    def test_carton_larger_than_pallet_both_dims(self):
        ti, _ = find_optimal_arrangement(50, 45, PL, PW)
        assert ti == 0

    def test_24x20_large_uniform(self):
        # floor(48/24)×floor(40/20)=2×2=4
        ti, _ = find_optimal_arrangement(24, 20, PL, PW)
        assert ti == 4

    def test_zero_carton_dimension(self):
        ti, config = find_optimal_arrangement(0, 8, PL, PW)
        assert ti == 0
        assert config is None


# ── Hi (layers high) ─────────────────────────────────────────

class TestHi:
    def test_standard_hi_12x8x6(self):
        # available = 60 - 5.5 = 54.5 → floor(54.5/6) = 9
        r = calculate(12, 8, 6, 60, PL, PW, PH)
        assert r['hi'] == 9

    def test_exact_fit_hi(self):
        # available = 60 - 5.5 = 54.5 → floor(54.5/10) = 5
        r = calculate(12, 8, 10, 60, PL, PW, PH)
        assert r['hi'] == 5

    def test_hi_never_affected_by_stacking(self):
        # Hi is always single-pallet only; stacking is a truckload-level concern
        r = calculate(12, 8, 6, 60, PL, PW, PH)
        # avail = 60 - 5.5 = 54.5 → floor(54.5/6) = 9, always
        assert r['hi'] == 9
        assert r['available_height'] == pytest.approx(54.5)

    def test_no_pallet_excludes_pallet_height(self):
        # Passing pallet_h=0 simulates the "No Pallet (DI)" toggle
        r_pallet   = calculate(12, 8, 6, 60, PL, PW, PH)
        r_nopallet = calculate(12, 8, 6, 60, PL, PW, 0.0)
        assert r_pallet['hi']   == 9
        assert r_nopallet['hi'] == 10  # floor(60/6)
        assert r_nopallet['available_height'] == 60.0

    def test_carton_too_tall_gives_hi_zero(self):
        # Carton taller than available height → can't stack any
        r = calculate(12, 8, 60, 60, PL, PW, PH)
        assert r['hi'] == 0
        assert r['total'] == 0

    def test_total_equals_ti_times_hi(self):
        r = calculate(14, 6, 5, 60, PL, PW, PH)
        assert r['total'] == r['ti'] * r['hi']

    def test_costco_spec_58in_max(self):
        # 58" max, 5.5" pallet → 52.5" available
        r = calculate(12, 8, 6, 58, PL, PW, PH)
        assert r['hi'] == 8   # floor(52.5/6) = 8
        assert r['available_height'] == pytest.approx(52.5)

    def test_amazon_spec_50in_max(self):
        # 50" max, 5.5" pallet → 44.5" available
        r = calculate(12, 8, 6, 50, PL, PW, PH)
        assert r['hi'] == 7   # floor(44.5/6) = 7


# ── Pod dimensions ────────────────────────────────────────────

class TestPodDimensions:
    def test_user_example_5x2_on_small_pallet(self):
        # 2×2 carton, 5 across × 2 deep on an 11×4.5 pallet → pod 10×4
        r = calculate(2, 2, 2, 20, 11, 4.5, 0)
        assert r['pod_length'] == 10.0
        assert r['pod_width']  == 4.0

    def test_perfect_packing_fills_pallet_floor(self):
        # 12×8 on 48×40: mixed pattern covers the full pallet
        r = calculate(12, 8, 6, 60, PL, PW, PH)
        assert r['pod_length'] == PL
        assert r['pod_width']  == PW

    def test_square_carton_pod_leaves_gap(self):
        # 10×10 on 48×40: 4 wide (40") but only 40" deep — no 48" span
        r = calculate(10, 10, 6, 60, PL, PW, PH)
        assert r['pod_length'] == 40.0
        assert r['pod_width']  == 40.0

    def test_6x6_pod_has_width_gap(self):
        # 6×6 on 48×40: 8 cols × 6 = 48 long; 6 rows × 6 = 36 wide (4" gap)
        r = calculate(6, 6, 4, 60, PL, PW, PH)
        assert r['pod_length'] == 48.0
        assert r['pod_width']  == 36.0

    def test_7x5_column_split_pod_length(self):
        # Col split: 6 cols × 7 + 1 col × 5 = 47 long; 8 rows × 5 = 40 wide
        r = calculate(7, 5, 3, 60, PL, PW, PH)
        assert r['pod_length'] == 47.0
        assert r['pod_width']  == 40.0

    def test_pod_length_never_exceeds_pallet(self):
        for cl, cw in [(12, 8), (10, 10), (14, 6), (7, 5), (6, 6)]:
            r = calculate(cl, cw, 6, 60, PL, PW, PH)
            assert r['pod_length'] <= PL, f"{cl}×{cw}: pod_length {r['pod_length']} > pallet {PL}"
            assert r['pod_width']  <= PW, f"{cl}×{cw}: pod_width {r['pod_width']} > pallet {PW}"

    def test_pod_zero_when_ti_zero(self):
        r = calculate(50, 45, 6, 60, PL, PW, PH)
        assert r['ti'] == 0
        assert r['pod_length'] == 0.0
        assert r['pod_width']  == 0.0


# ── Efficiency ────────────────────────────────────────────────

class TestEfficiency:
    def test_100_percent_12x8(self):
        # 20 × (12×8) = 1920 = 48×40 → 100%
        r = calculate(12, 8, 6, 60, PL, PW, PH)
        assert r['efficiency'] == pytest.approx(1.0)

    def test_100_percent_8x8(self):
        # 30 × (8×8) = 1920 = 48×40 → 100%
        r = calculate(8, 8, 6, 60, PL, PW, PH)
        assert r['efficiency'] == pytest.approx(1.0)

    def test_partial_efficiency_10x10(self):
        # 16 × (10×10) = 1600 / 1920 ≈ 83.3%
        r = calculate(10, 10, 6, 60, PL, PW, PH)
        assert r['efficiency'] == pytest.approx(1600 / 1920, abs=1e-4)

    def test_partial_efficiency_6x6(self):
        # 48 × (6×6) = 1728 / 1920 = 90%
        r = calculate(6, 6, 4, 60, PL, PW, PH)
        assert r['efficiency'] == pytest.approx(1728 / 1920, abs=1e-4)

    def test_efficiency_between_0_and_1(self):
        for cl, cw in [(11, 9), (7, 5), (14, 6), (24, 20)]:
            r = calculate(cl, cw, 6, 60, PL, PW, PH)
            assert 0 < r['efficiency'] <= 1.0, f"{cl}×{cw}: efficiency {r['efficiency']}"

    def test_zero_ti_gives_zero_efficiency(self):
        r = calculate(50, 45, 6, 60, PL, PW, PH)
        assert r['efficiency'] == 0.0


# ── Arrangement descriptions ──────────────────────────────────

class TestArrangementDesc:
    def test_uniform_desc(self):
        r = calculate(8, 8, 6, 60, PL, PW, PH)
        assert 'Uniform' in r['arrangement_desc'] or 'Rotated' in r['arrangement_desc']

    def test_mixed_desc(self):
        r = calculate(14, 6, 5, 60, PL, PW, PH)
        assert 'Mixed' in r['arrangement_desc']

    def test_mixed_contains_counts(self):
        r = calculate(12, 8, 6, 60, PL, PW, PH)
        # Expected: "Mixed: 2×4 + 2×6"
        assert '×' in r['arrangement_desc']

    def test_zero_ti_desc(self):
        r = calculate(50, 45, 6, 60, PL, PW, PH)
        assert r['arrangement_desc'] is not None

    def test_arrangement_description_zero_ti(self):
        from calculator import arrangement_description
        desc = arrangement_description(None, 0)
        assert desc == "0 cases"


# ── Position generation ───────────────────────────────────────

class TestPositions:
    def test_position_count_matches_ti(self):
        for cl, cw in [(12, 8), (10, 10), (14, 6), (7, 5)]:
            r = calculate(cl, cw, 6, 60, PL, PW, PH)
            assert len(r['arrangement']) == r['ti'], \
                f"{cl}×{cw}: {len(r['arrangement'])} positions != Ti={r['ti']}"

    def test_positions_within_pallet_bounds(self):
        for cl, cw in [(12, 8), (10, 10), (14, 6), (7, 5), (6, 6)]:
            r = calculate(cl, cw, 6, 60, PL, PW, PH)
            for c in r['arrangement']:
                assert c['x'] >= 0
                assert c['y'] >= 0
                assert c['x'] + c['w'] <= PL + 1e-9, \
                    f"{cl}×{cw}: carton x+w={c['x']+c['w']} > pallet {PL}"
                assert c['y'] + c['h'] <= PW + 1e-9, \
                    f"{cl}×{cw}: carton y+h={c['y']+c['h']} > pallet {PW}"

    def test_no_positions_when_ti_zero(self):
        r = calculate(50, 45, 6, 60, PL, PW, PH)
        assert r['arrangement'] == []

    def test_generate_positions_no_config(self):
        from calculator import generate_positions
        assert generate_positions(None) == []

    def test_rotated_flag_present(self):
        r = calculate(12, 8, 6, 60, PL, PW, PH)
        assert all('rotated' in c for c in r['arrangement'])


# ── Truckload quantity (computed in app.py, tested here via helper) ──────────

def truckload(total, case_pack, pallets_per_floor, double_stack_allowed):
    """Mirror of the app.py truckload formula."""
    return case_pack * total * pallets_per_floor * (2 if double_stack_allowed else 1)


class TestTruckload:
    def test_user_example(self):
        # 4 units/carton × 5 cartons/pallet × 2 pallets/floor × 2 (stacking) = 80
        assert truckload(5, 4, 2, True) == 80

    def test_no_double_stack_no_multiplier(self):
        assert truckload(5, 4, 2, False) == 40

    def test_case_pack_1_default(self):
        # case_pack=1 means truckload == total × pallets × stack_mult
        assert truckload(180, 1, 26, False) == 180 * 26
        assert truckload(180, 1, 26, True)  == 180 * 26 * 2

    def test_double_stack_doubles_truckload(self):
        tl_single = truckload(100, 4, 26, False)
        tl_double = truckload(100, 4, 26, True)
        assert tl_double == tl_single * 2

    def test_proportional_to_case_pack(self):
        tl1 = truckload(100, 1, 26, False)
        tl4 = truckload(100, 4, 26, False)
        assert tl4 == tl1 * 4

    def test_proportional_to_pallets_per_floor(self):
        tl_26 = truckload(100, 4, 26, False)
        tl_20 = truckload(100, 4, 20, False)
        assert tl_26 / tl_20 == pytest.approx(26 / 20)

    def test_zero_total_gives_zero_truckload(self):
        assert truckload(0, 4, 26, True) == 0


class TestPlaceRing:
    ALL4 = ['front', 'back', 'left', 'right']

    def test_4sided_basic_counts(self):
        # pallet 48×40, case 10L×8W; front=40" side
        # front/back: floor(40/8)=5; left/right span=48-10-10=28, floor(28/8)=3
        ring = place_ring(10, 8, 48, 40, self.ALL4, rounding_gaps=True)
        assert ring is not None
        assert ring['counts']['front'] == 5
        assert ring['counts']['back']  == 5
        assert ring['counts']['left']  == 3
        assert ring['counts']['right'] == 3
        assert ring['total'] == 16

    def test_4sided_inner_rect(self):
        ring = place_ring(10, 8, 48, 40, self.ALL4, rounding_gaps=True)
        assert ring['inner_l'] == pytest.approx(28.0)
        assert ring['inner_w'] == pytest.approx(20.0)

    def test_ring3_fails_when_inner_dims_negative(self):
        # After rings 1+2 with case 10×8 on 48×40, inner rect shrinks to (8,0).
        # inner_l = 8 - 10*2 = -12 < 0 → None
        ring = place_ring(10, 8, 8, 0, self.ALL4, rounding_gaps=True)
        assert ring is None

    def test_rounding_gaps_false_rejects_gap(self):
        # left/right span=48-20=28, 28%8=4 → gap → None when rounding_gaps=False
        ring = place_ring(10, 8, 48, 40, self.ALL4, rounding_gaps=False)
        assert ring is None

    def test_rounding_gaps_false_accepts_clean_division(self):
        # case 8×8: front/back 40%8=0 ✓; left/right span=48-16=32, 32%8=0 ✓
        ring = place_ring(8, 8, 48, 40, self.ALL4, rounding_gaps=False)
        assert ring is not None
        assert ring['counts']['front'] == 5   # floor(40/8)=5
        assert ring['counts']['left']  == 4   # floor(32/8)=4

    def test_3sided_front_left_right(self):
        # front: floor(40/8)=5; left/right span=48-10=38, floor(38/8)=4
        ring = place_ring(10, 8, 48, 40, ['front', 'left', 'right'], rounding_gaps=True)
        assert ring is not None
        assert ring['counts']['front'] == 5
        assert ring['counts']['left']  == 4
        assert ring['counts']['right'] == 4
        assert 'back' not in ring['counts']
        assert ring['inner_l'] == pytest.approx(38.0)  # 48-10 (front eats case_l from L, no back)
        assert ring['inner_w'] == pytest.approx(20.0)  # 40-10-10 (left+right each eat case_l from W)

    def test_2sided_front_back_only(self):
        # front/back: floor(40/8)=5 each; no left/right
        ring = place_ring(10, 8, 48, 40, ['front', 'back'], rounding_gaps=True)
        assert ring is not None
        assert ring['counts']['front'] == 5
        assert ring['counts']['back']  == 5
        assert 'left'  not in ring['counts']
        assert 'right' not in ring['counts']
        assert ring['inner_l'] == pytest.approx(28.0)  # L shrinks by 2×case_l (front+back)
        assert ring['inner_w'] == pytest.approx(40.0)  # W unchanged (no left/right)

    def test_returns_none_when_inner_dims_negative(self):
        # rect 18×18, case 10: inner_l=18-10*2=-2 < 0 → None
        ring = place_ring(10, 8, 18, 18, self.ALL4, rounding_gaps=True)
        assert ring is None

    def test_returns_none_when_front_has_zero_cases(self):
        # rect_l=6, inner_l=6-10*2=-14 < 0 → None before front count is checked
        ring = place_ring(10, 8, 6, 40, ['front', 'back'], rounding_gaps=True)
        assert ring is None


class TestShoppableArrangement:
    ALL4 = ['front', 'back', 'left', 'right']

    def test_4sided_10x8_two_rings_pure_facing(self):
        # Axis: front=40" side. Ring 1 (48×40): 5+5+3+3=16 cases; inner 28×20.
        # Ring 2 (28×20): front/back=2, lr_span=8, n=1 → 6 cases; inner 8×0.
        # Ring 3 fails. Total=22. Void=8.3%<15% → pure_facing (no fill needed).
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4)
        assert result['ring_count'] == 2
        assert result['ti'] == 22
        assert result['mode'] == 'pure_facing'
        assert result['void_pct'] == pytest.approx((1920 - 22 * 80) / 1920, abs=1e-4)
        assert result['error'] is None

    def test_8x8_two_rings_pure_facing(self):
        # Ring 1 (48×40): front/back=5, lr_span=32, n=4 → 18 cases; inner 32×24
        # Ring 2 (32×24): front/back=3, lr_span=16, n=2 → 10 cases; inner 16×8
        # Ring 3 (16×8): lr_span=0 → None. Total 28. Void=128/1920=6.67%<15% → pure_facing
        result = find_shoppable_arrangement(8, 8, 48, 40, self.ALL4)
        assert result['ring_count'] == 2
        assert result['mode'] == 'pure_facing'
        assert result['void_pct'] == pytest.approx(128 / 1920, abs=1e-4)

    def test_force_fill_brings_within_limit(self):
        # case 12×10, 4-sided: Ring 1 (48×40): 4+4+2+2=12; inner 24×16; void=25%>15%
        # fill 24×16 with 12×10 → 2 cases; total=14; void=12.5%<15% → filled
        result = find_shoppable_arrangement(12, 10, 48, 40, self.ALL4, max_empty_pct=0.15)
        assert result['mode'] == 'filled'
        assert result['void_pct'] < 0.15

    def test_error_when_void_exceeds_limit_after_fill(self):
        # Very large cases (20×20): left/right span=0 on first ring → 0 rings placed
        result = find_shoppable_arrangement(20, 20, 48, 40, self.ALL4, max_empty_pct=0.10)
        assert result['mode'] == 'error'
        assert result['error'] is not None

    def test_partial_mode_when_force_fill_off(self):
        result = find_shoppable_arrangement(
            10, 8, 48, 40, self.ALL4,
            force_fill_on_failure=False
        )
        assert result['mode'] == 'partial'
        assert result['ring_count'] == 2  # 2 rings placed before inner rect exhausted

    def test_3sided_front_left_right(self):
        result = find_shoppable_arrangement(10, 8, 48, 40, ['front', 'left', 'right'])
        assert result['ring_count'] >= 1
        assert result['ti'] > 0
        assert result['mode'] in ('pure_facing', 'filled', 'partial')

    def test_rounding_gaps_false_zero_rings_then_error(self):
        # 10×8 on 48×40: left/right span=20, 20%8=4 → gap → 0 rings placed
        result = find_shoppable_arrangement(
            10, 8, 48, 40, self.ALL4, rounding_gaps=False
        )
        assert result['ring_count'] == 0
        assert result['mode'] == 'error'

    def test_ti_never_exceeds_standard_ti(self):
        from calculator import find_optimal_arrangement
        ti_standard, _ = find_optimal_arrangement(10, 8, 48, 40)
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4)
        assert result['ti'] <= ti_standard

    def test_void_pct_in_0_to_1_range(self):
        result = find_shoppable_arrangement(10, 8, 48, 40, self.ALL4)
        assert 0.0 <= result['void_pct'] <= 1.0


class TestRingPositions:
    """
    Validate generate_ring_positions() by checking exact coordinates.
    Known input: 48L x 40W pallet, case 4L x 2.3W, all 4 sides.
    Front = 40" side (W); front/back span W, left/right span L.
    Gap placement: pack from both ends, gap falls in the middle of each strip.
      Ring 1 (48Lx40W @ 0,0): front=17@y=0, back=17@y=44, left=17@x=0, right=17@x=36
      Ring 2 (40Lx32W @ 4,4): front=13@y=4, back=13@y=40, left=13@x=4, right=13@x=32
      Ring 3 (32Lx24W @ 8,8): front=10@y=8, back=10@y=36, left=10@x=8, right=10@x=28
      Ring 4 (24Lx16W @ 12,12): front=6@y=12, back=6@y=32, left=6@x=12, right=6@x=24
      Ring 5 (16Lx8W @ 16,16): front=3@y=16, back=3@y=28, left=3@x=16, right=3@x=20
    Pack-from-both-ends: k=n//2 flush at start, n-k flush at end, gap in the middle.
    """
    ALL4 = ['front', 'back', 'left', 'right']
    CL, CW = 4.0, 2.3

    def _pos(self):
        return generate_ring_positions(self.CL, self.CW, 48, 40, self.ALL4)

    # ── Ring 1 ────────────────────────────────────────────────

    def test_ring1_front_count_and_first_position(self):
        front = [p for p in self._pos() if p['ring'] == 1 and p['side'] == 'front']
        assert len(front) == 17          # floor(40/2.3)=17
        # pack-from-both-ends: k=8 flush at x=0, n-k=9 flush ending at 40"
        assert front[0]['x'] == pytest.approx(0.0)
        assert front[0]['y'] == pytest.approx(0.0)
        assert front[0]['w'] == pytest.approx(2.3)
        assert front[0]['h'] == pytest.approx(4.0)

    def test_ring1_front_x_spacing(self):
        # pack-from-both-ends: gap=0.9, k=8 cases at x=[0..16.1], then 9 cases at x=[19.3..37.7]
        front = [p for p in self._pos() if p['ring'] == 1 and p['side'] == 'front']
        xs = [p['x'] for p in front]
        gap = 40 - 17 * 2.3
        k = 8
        expected = [i * 2.3 for i in range(k)] + [k * 2.3 + gap + i * 2.3 for i in range(17 - k)]
        assert xs == pytest.approx(expected, abs=1e-5)

    def test_ring1_back_y_at_bottom(self):
        # back strip y = oy + rect_l - case_l = 0 + 48 - 4 = 44
        back = [p for p in self._pos() if p['ring'] == 1 and p['side'] == 'back']
        assert len(back) == 17
        assert all(p['y'] == pytest.approx(44.0) for p in back)

    def test_ring1_left_x_and_y_start(self):
        # left: x=0; lr_span=40, pack-from-both-ends, first case at y=y_offset=4
        left = [p for p in self._pos() if p['ring'] == 1 and p['side'] == 'left']
        assert len(left) == 17
        assert all(p['x'] == pytest.approx(0.0) for p in left)
        assert left[0]['y'] == pytest.approx(4.0)
        assert left[0]['w'] == pytest.approx(4.0)
        assert left[0]['h'] == pytest.approx(2.3)

    def test_ring1_right_x(self):
        # right: x = ox + rect_w - case_l = 0 + 40 - 4 = 36
        right = [p for p in self._pos() if p['ring'] == 1 and p['side'] == 'right']
        assert len(right) == 17
        assert all(p['x'] == pytest.approx(36.0) for p in right)

    # ── Ring 2 ────────────────────────────────────────────────

    def test_ring2_front_offset(self):
        # Ring 2: ox=4, oy=4, rect_w=32; front n=13, pack-from-both-ends, first x=ox=4
        front = [p for p in self._pos() if p['ring'] == 2 and p['side'] == 'front']
        assert len(front) == 13          # floor(32/2.3)=13
        assert front[0]['x'] == pytest.approx(4.0)
        assert front[0]['y'] == pytest.approx(4.0)

    def test_ring2_back_y(self):
        # Ring 2: oy=4, rect_l=40 → back y = 4 + 40 - 4 = 40
        back = [p for p in self._pos() if p['ring'] == 2 and p['side'] == 'back']
        assert all(p['y'] == pytest.approx(40.0) for p in back)

    def test_ring2_left_x_and_y_start(self):
        # Ring 2: ox=4; lr_span=32, n=13, pack-from-both-ends, first y=oy+y_offset=4+4=8
        left = [p for p in self._pos() if p['ring'] == 2 and p['side'] == 'left']
        assert len(left) == 13           # floor(32/2.3)=13
        assert all(p['x'] == pytest.approx(4.0) for p in left)
        assert left[0]['y'] == pytest.approx(8.0)

    def test_ring2_right_x(self):
        # Ring 2: ox=4, rect_w=32 → right x = 4 + 32 - 4 = 32
        right = [p for p in self._pos() if p['ring'] == 2 and p['side'] == 'right']
        assert all(p['x'] == pytest.approx(32.0) for p in right)

    # ── Ring counts ───────────────────────────────────────────

    def test_ring5_exists_ring6_does_not(self):
        rings = set(p['ring'] for p in self._pos())
        assert 5 in rings
        assert 6 not in rings

    def test_total_cases_matches_find_shoppable(self):
        positions = self._pos()
        result = find_shoppable_arrangement(self.CL, self.CW, 48, 40, self.ALL4)
        assert len(positions) == result['ti']

    def test_no_fill_cases_in_pure_facing_mode(self):
        # pure_facing: void within limit, no fill triggered
        result = find_shoppable_arrangement(self.CL, self.CW, 48, 40, self.ALL4)
        assert result['mode'] == 'pure_facing'
        fill = [p for p in self._pos() if p['ring'] == 0]
        assert fill == []

    # ── Fill positions ────────────────────────────────────────

    def test_fill_positions_present_in_filled_mode(self):
        # case 12x10, 4-sided: ring_count=1 (12 cases), void=25% → filled mode
        result = find_shoppable_arrangement(12, 10, 48, 40, self.ALL4)
        assert result['mode'] == 'filled'
        positions = generate_ring_positions(12, 10, 48, 40, self.ALL4)
        fill = [p for p in positions if p['ring'] == 0]
        assert len(fill) > 0
        # Fill origin: ox=12 (left strip), oy=12 (front strip)
        assert all(p['x'] >= 12.0 - 1e-9 for p in fill)
        assert all(p['y'] >= 12.0 - 1e-9 for p in fill)

    def test_fill_count_matches_ti_delta(self):
        ring_result = find_shoppable_arrangement(12, 10, 48, 40, self.ALL4)
        positions = generate_ring_positions(12, 10, 48, 40, self.ALL4)
        ring_only = sum(1 for p in positions if p['ring'] > 0)
        fill_only = sum(1 for p in positions if p['ring'] == 0)
        assert ring_only + fill_only == ring_result['ti']

    # ── 2-sided (front/back only) ─────────────────────────────

    def test_2sided_no_left_right_cases(self):
        positions = generate_ring_positions(4, 2.3, 48, 40, ['front', 'back'])
        assert all(p['side'] in ('front', 'back') for p in positions)

    def test_2sided_ring2_ox_stays_at_zero(self):
        # No left strip → ox never advances → ring 2 front starts at ox=0
        # ring1: rect_w=40, inner_w=40 (no LR); ring2: rect_w=40 still, gap still 0.9
        positions = generate_ring_positions(4, 2.3, 48, 40, ['front', 'back'])
        front_r2 = [p for p in positions if p['ring'] == 2 and p['side'] == 'front']
        assert front_r2[0]['x'] == pytest.approx(0.0)   # pack-from-both-ends, ox=0
        assert front_r2[0]['y'] == pytest.approx(4.0)   # oy=4 after ring 1 front

    # ── Error mode ────────────────────────────────────────────

    def test_empty_when_no_ring_fits(self):
        # Cases too large to form any ring
        positions = generate_ring_positions(25, 25, 48, 40, self.ALL4)
        assert positions == []
