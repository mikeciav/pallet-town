"""Pallet Town — Flask application."""

import json
import os
from flask import Flask, jsonify, render_template, request
from calculator import calculate

app = Flask(__name__)

RETAILERS_FILE = os.path.join(os.path.dirname(__file__), "retailers.json")

# Fixed pallet dimensions — not configurable per retailer
PALLET_L = 48.0
PALLET_W = 40.0
PALLET_H = 5.5

DEFAULT_RETAILERS = [
    {"id": 1,  "name": "Walmart",        "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 2,  "name": "Target",         "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 3,  "name": "Costco",         "max_height": 58, "double_stack_allowed": True,  "max_pallets_per_floor": 26},
    {"id": 4,  "name": "Amazon",         "max_height": 50, "double_stack_allowed": True,  "max_pallets_per_floor": 26},
    {"id": 5,  "name": "Home Depot",     "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 6,  "name": "Lowe's",         "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 7,  "name": "Kroger",         "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 8,  "name": "Sam's Club",     "max_height": 60, "double_stack_allowed": True,  "max_pallets_per_floor": 26},
    {"id": 9,  "name": "Dollar General", "max_height": 57, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 10, "name": "Dollar Tree",    "max_height": 57, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 11, "name": "Walgreens",      "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 12, "name": "CVS",            "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 13, "name": "Best Buy",       "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 14, "name": "Whole Foods",    "max_height": 60, "double_stack_allowed": False, "max_pallets_per_floor": 26},
    {"id": 15, "name": "BJ's Wholesale", "max_height": 60, "double_stack_allowed": True,  "max_pallets_per_floor": 26},
]


def load_retailers():
    if os.path.exists(RETAILERS_FILE):
        with open(RETAILERS_FILE) as f:
            return json.load(f)
    return DEFAULT_RETAILERS.copy()


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
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/retailers", methods=["GET"])
def api_retailers_list():
    return jsonify(load_retailers())


@app.route("/api/retailers", methods=["POST"])
def api_retailers_create():
    data = request.get_json(force=True) or {}
    retailers = load_retailers()
    new_id = max((r["id"] for r in retailers), default=0) + 1
    retailer = {"id": new_id, **_parse_retailer_body(data)}
    retailers.append(retailer)
    save_retailers(retailers)
    return jsonify(retailer), 201


@app.route("/api/retailers/<int:rid>", methods=["PUT"])
def api_retailers_update(rid: int):
    data = request.get_json(force=True) or {}
    retailers = load_retailers()
    for r in retailers:
        if r["id"] == rid:
            r.update(_parse_retailer_body(data, r))
            save_retailers(retailers)
            return jsonify(r)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/retailers/<int:rid>", methods=["DELETE"])
def api_retailers_delete(rid: int):
    retailers = [r for r in load_retailers() if r["id"] != rid]
    save_retailers(retailers)
    return "", 204


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(force=True) or {}
    try:
        carton_l = float(data["length"])
        carton_w = float(data["width"])
        carton_h = float(data["height"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "length, width, height are required numbers"}), 400

    if carton_l <= 0 or carton_w <= 0 or carton_h <= 0:
        return jsonify({"error": "Dimensions must be positive"}), 400

    retailers = load_retailers()
    retailer = next((r for r in retailers if str(r["id"]) == str(data.get("retailer_id"))), None)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    exclude_pallet  = bool(data.get("exclude_pallet_height", False))
    case_pack_qty   = max(1, int(data.get("case_pack_qty", 1)))
    result = calculate(
        carton_l=carton_l,
        carton_w=carton_w,
        carton_h=carton_h,
        max_height=retailer["max_height"],
        pallet_l=PALLET_L,
        pallet_w=PALLET_W,
        pallet_h=0.0 if exclude_pallet else PALLET_H,
        double_stack=bool(data.get("double_stack", False)),
    )
    stack_mult = 2 if retailer["double_stack_allowed"] else 1
    result["truckload_qty"] = (
        case_pack_qty * result["total"] * retailer["max_pallets_per_floor"] * stack_mult
    )
    result["case_pack_qty"]        = case_pack_qty
    result["max_pallets_per_floor"] = retailer["max_pallets_per_floor"]
    result["stack_multiplier"]      = stack_mult
    return jsonify(result)


@app.route("/api/calculate-bulk", methods=["POST"])
def api_calculate_bulk():
    data = request.get_json(force=True) or {}

    retailers = load_retailers()
    retailer = next((r for r in retailers if str(r["id"]) == str(data.get("retailer_id"))), None)
    if not retailer:
        return jsonify({"error": "Retailer not found"}), 404

    cartons = data.get("cartons", [])
    if not cartons:
        return jsonify({"error": "No cartons provided"}), 400

    double_stack    = bool(data.get("double_stack", False))
    exclude_pallet  = bool(data.get("exclude_pallet_height", False))
    stack_mult      = 2 if retailer["double_stack_allowed"] else 1
    max_pallets     = retailer["max_pallets_per_floor"]
    results = []
    for carton in cartons:
        try:
            l = float(carton["length"])
            w = float(carton["width"])
            h = float(carton["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if l <= 0 or w <= 0 or h <= 0:
            continue

        case_pack_qty = max(1, int(carton.get("case_pack_qty", data.get("case_pack_qty", 1))))
        r = calculate(
            carton_l=l, carton_w=w, carton_h=h,
            max_height=retailer["max_height"],
            pallet_l=PALLET_L,
            pallet_w=PALLET_W,
            pallet_h=0.0 if exclude_pallet else PALLET_H,
            double_stack=double_stack,
        )
        r["truckload_qty"]        = case_pack_qty * r["total"] * max_pallets * stack_mult
        r["case_pack_qty"]        = case_pack_qty
        r["max_pallets_per_floor"] = max_pallets
        r["stack_multiplier"]      = stack_mult
        results.append({
            "sku": str(carton.get("sku", "")),
            "length": l, "width": w, "height": h,
            **r,
        })

    return jsonify(results)


if __name__ == "__main__":
    if not os.path.exists(RETAILERS_FILE):
        save_retailers(DEFAULT_RETAILERS)
    app.run(debug=True, port=5001)
