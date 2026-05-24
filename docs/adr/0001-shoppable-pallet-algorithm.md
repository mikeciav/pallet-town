# Shoppable pallet concentric-ring algorithm design

We chose a **concentric rings** approach for shoppable pallet layouts rather than a single border frame
followed by standard fill. Rings are placed outward-in, each `case_l` deep, until the interior is too
small to sustain another full ring. This was chosen because it maximises the number of shoppable layers
a shopper encounters as they work through the pallet — a single border frame with an unoriented chimney
only guarantees one shoppable layer and fails the retailer intent.

## Key algorithm decisions

**Ring connectivity (`rounding_gaps`, default `true`)**
Flush rings that leave small rounding gaps at strip ends are allowed by default. Perfectly connected rings
(no gaps, sized so `(pallet_w - 2×case_l) mod case_w == 0`) require `rounding_gaps = false`. We defaulted
to allowing gaps because club store guidelines (Sam's Club, BJ's) specify a void *percentage* limit, not
zero-gap continuity, and forcing connected-only rings would silently fail on most real case dimensions.

**Failure behaviour (`force_fill_on_failure`, default `true`)**
When the interior rectangle is too small to satisfy all selected shoppable sides, two behaviours are
supported:
- `true` — pack the remaining space with the standard orientation-free optimizer (maximises Ti in the chimney)
- `false` — extend the ring on whatever sides still fit at least one case, then leave the centre as a
  chimney

`false` was kept as an option specifically to satisfy club retailers that want an open chimney and prefer
a partial ring on feasible sides over a packed interior.

**Hard rule (not configurable)**
Every selected shoppable side must have at least one case anywhere on the pallet. If a side can never
yield a case, the feature should surface an error rather than silently omit that side from the result.

**Defaults chosen from retailer guidelines**
- `max_empty_pct`: 15% (Sam's Club industry guidance)
- `min_footprint`: 37"×45" (derived from BJ's 38"×44" official minimum coverage spec, section 1.16)
- Shoppable sides default: 3 for Sam's Club, 2 for BJ's (per their respective published guidelines)

## Considered and rejected

**Single border frame + standard chimney fill** — rejected because it only produces one shoppable layer.
Once the border layer is depleted, subsequent cases face inward or are packed for density, not shoppability.

**Flush-only rings with rounding gaps always permitted** — rejected as the default because it produces
visually disconnected corners on some case/pallet dimension combinations. `rounding_gaps = false` is
available as a toggle for retailers that care about ring continuity.
