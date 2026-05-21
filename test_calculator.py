"""
Unit tests for the pallet calculator.

Run with:  python3 -m pytest test_calculator.py -v
"""

import pytest
from calculator import calculate, find_optimal_arrangement, pod_dimensions, generate_positions

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
