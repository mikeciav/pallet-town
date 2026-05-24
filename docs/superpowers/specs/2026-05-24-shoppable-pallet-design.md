# Shoppable Pallet Design

**Date:** 2026-05-24  
**Status:** Approved  
**Branch:** feature/shoppable-pallet (to be created)

---

## Overview

Add a shoppable pallet calculator for club store retailers (Sam's Club, Costco, BJ's Wholesale). When a club store is selected, the user can configure which sides of the pallet are shoppable. The algorithm places concentric rings of cases with the shoppable face (`case_w`) oriented outward, then force-fills or leaves the chimney depending on configuration. Both standard Ti and shoppable Ti are shown in results.

Scoped to club stores only. Bulk import is excluded.

---

## Section 1 — Algorithm

### Concept

Cases on shoppable sides are oriented with `case_w` facing outward and `case_l` as depth going inward. Rings are placed concentrically (outermost first), each `case_l` deep, until the interior rectangle is too small to sustain another full ring. The remaining interior is either force-filled with the standard optimizer or left as a chimney.

### Ring placement

For each ring iteration, given the current rectangle (`rect_l × rect_w`):

- **Long-side strips** (spanning `rect_l`): `floor(rect_l / case_w)` cases per strip, `case_l` deep
- **Short-side strips** (between the long-side corners): `floor((rect_w - 2×case_l) / case_w)` cases per strip, `case_l` deep
- Shoppable sides are kept flush with the pallet edges; no centering logic is needed

A ring is valid only if every selected shoppable side yields ≥1 case. If any selected side yields 0 cases, ring placement stops and the fallback behaviour applies.

**Hard rule (not configurable):** every selected shoppable side must have ≥1 case somewhere on the pallet for the result to be reported as shoppable on that side.

### Parameters (all per-calculation, all toggleable)

| Parameter | Default | Description |
|---|---|---|
| `sides` | required (UI pre-populates from retailer conventions) | Which sides are shoppable: any non-empty subset of `{front, back, left, right}` |
| `max_empty_pct` | 15% | Maximum void as a fraction of total pallet area. Force-fill triggers when exceeded. |
| `rounding_gaps` | `true` | Allow flush rings where `(available_strip_length % case_w) ≠ 0`, leaving small end gaps. When `false`, only place rings whose dimensions divide evenly (no gaps). |
| `min_footprint` | [37, 45] | Total case layout (ring + fills) must span at least these dimensions (inches). Shorter pallet dimension maps to first value. |
| `force_fill_on_failure` | `true` | When no further full rings can be placed: `true` = pack remaining interior with standard optimizer (no orientation constraint); `false` = extend the ring on whatever sides still fit ≥1 case, leave centre as chimney. Locked to `true` when retailer `chimney_allowed: false`. |

### Result modes

| Mode | Meaning |
|---|---|
| `pure_facing` | All rings placed, void within `max_empty_pct`, no force-fill needed |
| `filled` | Rings placed, interior force-filled to stay within `max_empty_pct` |
| `partial` | `force_fill_on_failure: false` path — partial ring on feasible sides, open chimney |
| `error` | Constraints cannot be met even after force-fill |

### Retailer defaults

| Retailer | Default sides | `chimney_allowed` |
|---|---|---|
| Sam's Club | front, left, right | false |
| Costco | front, left, right | false |
| BJ's Wholesale | front, back | false |

---

## Section 2 — Data Model

### retailers.json — new fields

```json
{
  "is_club_store": false,
  "chimney_allowed": false
}
```

`is_club_store` defaults to `false`. Controls whether the shoppable UI appears and whether `/api/calculate` accepts a `shoppable` block.

`chimney_allowed` is retailer policy. When `false`: `force_fill_on_failure` is locked to `true` server-side and disabled in the UI with a tooltip.

**Backfill:** Sam's Club, Costco, BJ's Wholesale → `is_club_store: true`, `chimney_allowed: false`. All other retailers → `is_club_store: false`, `chimney_allowed: false`.

### `/api/calculate` request

New optional `shoppable` block. If sent for a retailer where `is_club_store: false` (including custom retailers), the endpoint returns 400.

```json
{
  "length": 10,
  "width": 8,
  "height": 6,
  "retailer_id": "8",
  "shoppable": {
    "sides": ["front", "left", "right"],
    "max_empty_pct": 0.15,
    "rounding_gaps": true,
    "min_footprint": [37, 45],
    "force_fill_on_failure": true
  }
}
```

If `shoppable` is absent, the endpoint behaves exactly as today.

### `/api/calculate` response

`total` is unchanged (standard Ti). A `shoppable` object is added when the `shoppable` block was present in the request.

```json
{
  "total": 24,
  "shoppable": {
    "ti": 20,
    "mode": "pure_facing",
    "void_pct": 0.12,
    "ring_count": 2,
    "error": null
  }
}
```

On `error` mode, `ti` is 0 and `error` contains a human-readable message.

---

## Section 3 — UI

### Club Display Options panel

Expands inline on the Calculator tab when a club store retailer is selected. Hidden for all other retailers.

**Controls:**

1. **Side selector** — four toggle buttons: Front / Back / Left / Right. At least 1 must be selected at all times. Pre-populated from retailer defaults when the panel first appears.
2. **Max empty %** — numeric input, default 15.
3. **Rounding gaps** — toggle (on by default).
4. **Min footprint** — two numeric inputs (W × L), defaults 37 × 45.
5. **Fill chimney** (`force_fill_on_failure`) — toggle (on by default). Disabled with a hover tooltip *"[Retailer name] does not permit open chimneys"* when retailer `chimney_allowed: false`.

### Results

Shoppable Ti is shown alongside standard Ti when the panel is active.

- Standard Ti and shoppable Ti displayed in the same results area as a two-row or two-column comparison
- Void %, ring count, and mode badge shown beneath shoppable Ti
- On `error` mode: shoppable Ti shows 0 and a red error banner appears above the results with the error message from the API

---

## Out of scope

- Bulk import shoppable support
- Per-retailer default `sides` stored on the retailer object (sides are always set per-calculation, with UI pre-populated from known retailer conventions)
- Custom retailer shoppable support
