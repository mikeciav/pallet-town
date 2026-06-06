"""Pallet Town — Flask application."""

import json
import os
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash
from calculator import calculate, find_shoppable_v2, generate_shoppable_v2_positions

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-in-production")
ADMIN_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

_data_dir = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
RETAILERS_FILE = os.path.join(_data_dir, "retailers.json")

# Fixed pallet dimensions — not configurable per retailer
PALLET_L = 48.0
PALLET_W = 40.0
PALLET_H = 5.5

# Feature flags
SHOW_DIAGRAM = True   # diagram panel (Ti top-down view)
SHOW_HI_VIEW = False  # Hi isometric toggle button inside the diagram panel
SHOW_DEMO_DEFAULTS = os.environ.get("SHOW_DEMO_DEFAULTS", "false").lower() == "true"

DEFAULT_RETAILERS = [
    {"id": 4,  "name": "Amazon",         "max_height": 50,   "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 13, "name": "Best Buy",       "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 15, "name": "BJ's Wholesale", "max_height": 60,   "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": True,  "chimney_allowed": False},
    {"id": 3,  "name": "Costco",         "max_height": 58.0, "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": True,  "chimney_allowed": True},
    {"id": 12, "name": "CVS",            "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 9,  "name": "Dollar General", "max_height": 57,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 10, "name": "Dollar Tree",    "max_height": 57,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 5,  "name": "Home Depot",     "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 7,  "name": "Kroger",         "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 6,  "name": "Lowe's",         "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 8,  "name": "Sam's Club",     "max_height": 60,   "double_stack_allowed": True,  "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": True,  "chimney_allowed": True},
    {"id": 2,  "name": "Target",         "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 11, "name": "Walgreens",      "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 1,  "name": "Walmart",        "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
    {"id": 14, "name": "Whole Foods",    "max_height": 60,   "double_stack_allowed": False, "max_pallets_per_floor": 26, "no_pallet": False, "notes": "", "is_club_store": False, "chimney_allowed": False},
]


def load_retailers():
    if os.path.exists(RETAILERS_FILE):
        with open(RETAILERS_FILE) as f:
            data = json.load(f)
        # Backfill any fields added after initial schema
        for r in data:
            r.setdefault("notes", "")
            r.setdefault("is_club_store", False)
            r.setdefault("chimney_allowed", False)
    else:
        data = [dict(r) for r in DEFAULT_RETAILERS]
    data.sort(key=lambda r: r["name"].casefold())
    return data


def save_retailers(retailers) -> None:
    with open(RETAILERS_FILE, "w") as f:
        json.dump(retailers, f, indent=2)


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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", show_diagram=SHOW_DIAGRAM, show_hi_view=SHOW_HI_VIEW,
                           show_demo_defaults=SHOW_DEMO_DEFAULTS)


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/api/auth/status")
def auth_status():
    return jsonify({"is_admin": bool(session.get("is_admin"))})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    if not ADMIN_HASH:
        return jsonify({"error": "Admin not configured on server"}), 500
    pw = (request.get_json(force=True) or {}).get("password", "")
    if check_password_hash(ADMIN_HASH, pw):
        session["is_admin"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "Incorrect password"}), 401


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/retailers", methods=["GET"])
def api_retailers_list():
    return jsonify(load_retailers())


@app.route("/api/retailers", methods=["POST"])
@require_admin
def api_retailers_create():
    data = request.get_json(force=True) or {}
    retailers = load_retailers()
    new_id = max((r["id"] for r in retailers), default=0) + 1
    retailer = {"id": new_id, **_parse_retailer_body(data)}
    retailers.append(retailer)
    save_retailers(retailers)
    return jsonify(retailer), 201


@app.route("/api/retailers/<int:rid>", methods=["PUT"])
@require_admin
def api_retailers_update(rid: int):
    data = request.get_json(force=True) or {}
    retailers = load_retailers()
    for r in retailers:
        if r["id"] == rid:
            r.update(_parse_retailer_body(data, r))
            save_retailers(retailers)
            return jsonify(r)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/retailers/<int:rid>/notes", methods=["PATCH"])
def api_retailer_notes(rid: int):
    data = request.get_json(force=True) or {}
    retailers = load_retailers()
    for r in retailers:
        if r["id"] == rid:
            r["notes"] = str(data.get("notes", ""))
            save_retailers(retailers)
            return jsonify(r)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/retailers/<int:rid>", methods=["DELETE"])
@require_admin
def api_retailers_delete(rid: int):
    retailers = [r for r in load_retailers() if r["id"] != rid]
    save_retailers(retailers)
    return "", 204


VALID_SIDES = {"top", "bottom", "left", "right"}


def _parse_shoppable_block(data: dict, retailer: dict):
    """
    Parse and validate the 'shoppable' key from an /api/calculate request body.
    Returns (params_dict, error_str). If error_str is not None, reject with 400.
    """
    shoppable = data.get("shoppable")
    if shoppable is None:
        return None, None

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
    if shoppable_params is not None:
        shoppable_result = find_shoppable_v2(
            case_l=case_l,
            case_w=case_w,
            pallet_l=PALLET_L,
            pallet_w=PALLET_W,
            sides=shoppable_params["sides"],
        )
        shoppable_result["arrangement"] = generate_shoppable_v2_positions(
            case_l=case_l,
            case_w=case_w,
            pallet_l=PALLET_L,
            pallet_w=PALLET_W,
            sides=shoppable_params["sides"],
        )
        result["shoppable"] = shoppable_result
    return jsonify(result)


@app.route("/api/calculate-bulk", methods=["POST"])
def api_calculate_bulk():
    data = request.get_json(force=True) or {}

    retailer_id = str(data.get("retailer_id", ""))
    if retailer_id == "custom":
        try:
            retailer = {
                "max_height":            float(data.get("max_height", 60)),
                "double_stack_allowed":  bool(data.get("double_stack_allowed", False)),
                "max_pallets_per_floor": int(data.get("max_pallets_per_floor", 26)),
                "no_pallet":             bool(data.get("no_pallet", False)),
            }
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid custom retailer params"}), 400
    else:
        retailer = next((r for r in load_retailers() if str(r["id"]) == retailer_id), None)
        if not retailer:
            return jsonify({"error": "Retailer not found"}), 404

    cases = data.get("cases", [])
    if not cases:
        return jsonify({"error": "No cases provided"}), 400

    stack_mult = 2 if retailer["double_stack_allowed"] else 1
    max_pallets     = retailer["max_pallets_per_floor"]
    results = []
    for case in cases:
        try:
            l = float(case["length"])
            w = float(case["width"])
            h = float(case["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if l <= 0 or w <= 0 or h <= 0:
            continue

        case_pack_qty = max(1, int(case.get("case_pack_qty", data.get("case_pack_qty", 1))))
        r = calculate(
            case_l=l, case_w=w, case_h=h,
            max_height=retailer["max_height"],
            pallet_l=PALLET_L,
            pallet_w=PALLET_W,
            pallet_h=0.0 if retailer.get("no_pallet", False) else PALLET_H,
        )
        r["truckload_qty"]        = case_pack_qty * r["total"] * max_pallets * stack_mult
        r["case_pack_qty"]        = case_pack_qty
        r["max_pallets_per_floor"] = max_pallets
        r["stack_multiplier"]      = stack_mult
        results.append({
            "sku": str(case.get("sku", "")),
            "length": l, "width": w, "height": h,
            **r,
        })

    return jsonify(results)


if __name__ == "__main__":
    if not os.path.exists(RETAILERS_FILE):
        save_retailers(DEFAULT_RETAILERS)
    app.run(debug=True, port=5001)
