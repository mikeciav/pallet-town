# Shoppable pallet corner-spiral algorithm

Club stores sell pallets that customers shop directly from the floor, so cases on the shoppable sides must face label-out toward the shopper. We chose a **clockwise corner-spiral** approach over a simple border frame or concentric ring layout.

## Algorithm

Cases are placed in concentric loops, each `case_l` deep, working from the outside in:

1. **TOP** (→): pack regular cases (`case_w` wide × `case_l` deep) left-to-right, leaving room for one corner case at the right end.
2. **RIGHT** (↑): pack regular cases (`case_l` wide × `case_w` tall) top-to-bottom, leaving room for one corner case at the bottom (omitted when `sides < 3`).
3. **BOTTOM** (←): mirror of top, packed right-to-left (omitted when `sides < 3`).
4. **LEFT** (↓): mirror of right, packed bottom-to-top, no trailing corner (omitted when `sides < 4`).

After each full loop the bounding box shrinks inward by `case_l` on each active side. Looping stops when the remaining interior is too small for another full loop (`2 × case_l > interior width or height`). The leftover interior is always filled with a standard orientation-free chimney fill to maximise Ti.

`Decimal` arithmetic is used throughout to prevent accumulated floating-point drift across many loop iterations.

## Key decisions

**Sides toggle (0 / 2 / 3 / 4)**
Retailers differ on how many sides need to be shoppable. 0 bypasses the spiral entirely and routes to the standard optimal layout. BJ's Wholesale defaults to 2; all other club stores default to 4.

**Ti = `len(arrangement)`**
Ti is read directly from the generated position list. There is no separate optimization call — the spiral defines both the layout and the case count.

**Chimney always filled**
The interior space left after the spiral is always packed with the standard optimizer. An open-chimney option was removed: partial fill wastes space without a meaningful retailer justification.

**Soft checks, not hard failures**
Max empty % and min footprint are shown as visual warnings (bold red) in the diagram header when violated, rather than rejecting the calculation. Real-world case dimensions often can't satisfy both constraints simultaneously, and surfacing the numbers is more useful than blocking the result.

**Defaults from retailer guidelines**
- `max_empty_pct`: 15% (Sam's Club guidance)
- `min_footprint`: 37" × 45" (derived from BJ's 38" × 44" official minimum, section 1.16)

## Considered and rejected

**Concentric rings** — the original implementation. Rings placed each side independently, leading to complex rounding-gap logic and a `rounding_gaps` toggle. Replaced because the gap logic was brittle across asymmetric case dimensions, and the corner-spiral naturally handles corners without per-side gap calculations.

**`rounding_gaps` toggle** — removed. Club store guidelines specify a void *percentage* limit, not zero-gap continuity, so forcing gap-free rings silently failed on most real dimensions without buyer benefit.

**`force_fill_on_failure` toggle** — removed. The chimney is always filled; the toggle existed only for the open-chimney use case, which was dropped.

**Single border frame + standard chimney** — rejected early. Produces only one shoppable layer; once the border is depleted subsequent cases face inward.
