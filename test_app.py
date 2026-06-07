"""
Integration tests for the Flask application.

Covers: auth endpoints, retailer CRUD, notes PATCH, calculate (preset + custom),
bulk calculate, load_retailers backfill, and input validation.

Run with:  python3 -m pytest test_app.py -v
"""

import json
import os
import tempfile
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    # pbkdf2 hash of "testpass"
    "pbkdf2:sha256:1000000$qMuI4ltyUuCtXYIf$27adb147a630b0dee8aa5adcb0bee07274cbede422792b5a604deaf96cd7dd41",
)

import app as flask_app


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path):
    """Flask test client with an isolated retailers.json in a temp dir."""
    flask_app.app.config["TESTING"] = True
    flask_app.app.config["SECRET_KEY"] = "test-secret"
    original = flask_app.RETAILERS_FILE
    flask_app.RETAILERS_FILE = str(tmp_path / "retailers.json")
    with flask_app.app.test_client() as c:
        yield c
    flask_app.RETAILERS_FILE = original


@pytest.fixture
def admin_client(client):
    """Test client already authenticated as admin."""
    client.post(
        "/api/auth/login",
        data=json.dumps({"password": "testpass"}),
        content_type="application/json",
    )
    return client


# ── Auth ──────────────────────────────────────────────────────

class TestAuth:
    def test_status_logged_out(self, client):
        r = client.get("/api/auth/status")
        assert r.status_code == 200
        assert r.get_json()["is_admin"] is False

    def test_login_correct_password(self, client):
        r = client.post("/api/auth/login",
                        data=json.dumps({"password": "testpass"}),
                        content_type="application/json")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_status_logged_in(self, admin_client):
        r = admin_client.get("/api/auth/status")
        assert r.get_json()["is_admin"] is True

    def test_login_wrong_password(self, client):
        r = client.post("/api/auth/login",
                        data=json.dumps({"password": "wrong"}),
                        content_type="application/json")
        assert r.status_code == 401

    def test_login_no_hash_configured(self, client, monkeypatch):
        monkeypatch.setattr(flask_app, "ADMIN_HASH", "")
        r = client.post("/api/auth/login",
                        data=json.dumps({"password": "testpass"}),
                        content_type="application/json")
        assert r.status_code == 500

    def test_logout_clears_session(self, admin_client):
        admin_client.post("/api/auth/logout")
        r = admin_client.get("/api/auth/status")
        assert r.get_json()["is_admin"] is False


# ── Retailers CRUD ────────────────────────────────────────────

class TestRetailersCRUD:
    def test_list_returns_notes_field(self, client):
        r = client.get("/api/retailers")
        data = r.get_json()
        assert r.status_code == 200
        assert all("notes" in retailer for retailer in data)

    def test_create_requires_admin(self, client):
        r = client.post("/api/retailers",
                        data=json.dumps({"name": "Test"}),
                        content_type="application/json")
        assert r.status_code == 401

    def test_create_as_admin(self, admin_client):
        r = admin_client.post("/api/retailers",
                              data=json.dumps({"name": "New Retailer", "max_height": 55}),
                              content_type="application/json")
        assert r.status_code == 201
        body = r.get_json()
        assert body["name"] == "New Retailer"
        assert body["max_height"] == 55
        assert "notes" in body

    def test_update_requires_admin(self, client):
        r = client.put("/api/retailers/1",
                       data=json.dumps({"name": "X"}),
                       content_type="application/json")
        assert r.status_code == 401

    def test_update_as_admin(self, admin_client):
        r = admin_client.put("/api/retailers/1",
                             data=json.dumps({"name": "Updated", "max_height": 62,
                                              "max_pallets_per_floor": 24,
                                              "double_stack_allowed": True,
                                              "no_pallet": False}),
                             content_type="application/json")
        assert r.status_code == 200
        assert r.get_json()["name"] == "Updated"

    def test_update_unknown_id(self, admin_client):
        r = admin_client.put("/api/retailers/9999",
                             data=json.dumps({"name": "X"}),
                             content_type="application/json")
        assert r.status_code == 404

    def test_delete_requires_admin(self, client):
        r = client.delete("/api/retailers/1")
        assert r.status_code == 401

    def test_delete_as_admin(self, admin_client):
        r = admin_client.delete("/api/retailers/1")
        assert r.status_code == 204
        ids = [x["id"] for x in admin_client.get("/api/retailers").get_json()]
        assert 1 not in ids


# ── Notes PATCH ───────────────────────────────────────────────

class TestRetailerNotes:
    def test_patch_notes_no_auth_required(self, client):
        """Notes can be saved by any user, not just admin."""
        r = client.patch("/api/retailers/1/notes",
                         data=json.dumps({"notes": "pickup only"}),
                         content_type="application/json")
        assert r.status_code == 200
        assert r.get_json()["notes"] == "pickup only"

    def test_patch_notes_persists(self, client):
        client.patch("/api/retailers/1/notes",
                     data=json.dumps({"notes": "floor-loaded"}),
                     content_type="application/json")
        retailers = client.get("/api/retailers").get_json()
        walmart = next(r for r in retailers if r["id"] == 1)
        assert walmart["notes"] == "floor-loaded"

    def test_patch_notes_unknown_id(self, client):
        r = client.patch("/api/retailers/9999/notes",
                         data=json.dumps({"notes": "x"}),
                         content_type="application/json")
        assert r.status_code == 404


# ── load_retailers backfill ───────────────────────────────────

class TestLoadRetailersBackfill:
    def test_notes_backfilled_on_old_schema(self, tmp_path, monkeypatch):
        """Retailer records written before the notes field was added get notes=''."""
        old_data = [{"id": 1, "name": "Legacy", "max_height": 60,
                     "double_stack_allowed": False, "max_pallets_per_floor": 26,
                     "no_pallet": False}]  # no "notes" key
        f = tmp_path / "retailers.json"
        f.write_text(json.dumps(old_data))
        monkeypatch.setattr(flask_app, "RETAILERS_FILE", str(f))
        result = flask_app.load_retailers()
        assert result[0]["notes"] == ""


# ── Retailer club fields ──────────────────────────────────────

class TestRetailerClubFields:
    def test_club_stores_have_is_club_store_true(self, client):
        r = client.get('/api/retailers')
        retailers = r.get_json()
        for name in ("Sam's Club", "Costco", "BJ's Wholesale"):
            retailer = next(r for r in retailers if r['name'] == name)
            assert retailer['is_club_store'] is True, f"{name} should be is_club_store=True"
        # BJ's does not permit open chimneys; Sam's Club and Costco do
        bjs = next(r for r in retailers if r['name'] == "BJ's Wholesale")
        assert bjs['chimney_allowed'] is False
        for name in ("Sam's Club", "Costco"):
            retailer = next(r for r in retailers if r['name'] == name)
            assert retailer['chimney_allowed'] is True, f"{name} should be chimney_allowed=True"

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
        data = flask_app.load_retailers()
        assert data[0]['is_club_store'] is False
        assert data[0]['chimney_allowed'] is False


# ── Calculate (preset retailer) ───────────────────────────────

class TestCalculatePreset:
    def _post(self, client, body):
        return client.post("/api/calculate",
                           data=json.dumps(body),
                           content_type="application/json")

    def test_valid_calculation(self, client):
        r = self._post(client, {"length": 12, "width": 8, "height": 6,
                                "retailer_id": 1, "case_pack_qty": 4})
        assert r.status_code == 200
        d = r.get_json()
        assert d["ti"] == 20
        assert d["hi"] == 9        # (60 - 5.5) / 6 = 9
        assert d["total"] == 180
        assert d["truckload_qty"] == 4 * 180 * 26  # no double-stack for Walmart
        assert d["case_h"] == 6.0

    def test_missing_dimensions(self, client):
        r = self._post(client, {"retailer_id": 1})
        assert r.status_code == 400

    def test_zero_dimensions(self, client):
        r = self._post(client, {"length": 0, "width": 8, "height": 6, "retailer_id": 1})
        assert r.status_code == 400

    def test_unknown_retailer(self, client):
        r = self._post(client, {"length": 12, "width": 8, "height": 6, "retailer_id": 9999})
        assert r.status_code == 404

    def test_no_pallet_retailer(self, admin_client):
        """When no_pallet=True the full max_height is available."""
        admin_client.put("/api/retailers/1",
                         data=json.dumps({"name": "Walmart", "max_height": 60,
                                          "max_pallets_per_floor": 26,
                                          "double_stack_allowed": False,
                                          "no_pallet": True}),
                         content_type="application/json")
        r = admin_client.post("/api/calculate",
                              data=json.dumps({"length": 12, "width": 8, "height": 6,
                                               "retailer_id": 1}),
                              content_type="application/json")
        assert r.status_code == 200
        assert r.get_json()["hi"] == 10   # floor(60/6) with no pallet board

    def test_double_stack_doubles_truckload(self, client):
        r = self._post(client, {"length": 12, "width": 8, "height": 6,
                                "retailer_id": 3,  # Costco, double_stack=True
                                "case_pack_qty": 1})
        d = r.get_json()
        assert d["stack_multiplier"] == 2
        assert d["truckload_qty"] == d["total"] * 26 * 2

    def test_case_pack_scales_truckload(self, client):
        r1 = self._post(client, {"length": 12, "width": 8, "height": 6,
                                 "retailer_id": 1, "case_pack_qty": 1})
        r4 = self._post(client, {"length": 12, "width": 8, "height": 6,
                                 "retailer_id": 1, "case_pack_qty": 4})
        assert r4.get_json()["truckload_qty"] == r1.get_json()["truckload_qty"] * 4


# ── Calculate (custom retailer) ───────────────────────────────

class TestCalculateCustom:
    def _post(self, client, body):
        return client.post("/api/calculate",
                           data=json.dumps(body),
                           content_type="application/json")

    def test_custom_uses_inline_params(self, client):
        r = self._post(client, {
            "length": 12, "width": 8, "height": 6,
            "retailer_id": "custom",
            "max_height": 48,
            "double_stack_allowed": False,
            "max_pallets_per_floor": 20,
            "no_pallet": False,
            "case_pack_qty": 1,
        })
        assert r.status_code == 200
        d = r.get_json()
        assert d["hi"] == 7            # floor((48-5.5)/6) = 7
        assert d["max_pallets_per_floor"] == 20

    def test_custom_no_pallet(self, client):
        r = self._post(client, {
            "length": 12, "width": 8, "height": 6,
            "retailer_id": "custom",
            "max_height": 60,
            "double_stack_allowed": False,
            "max_pallets_per_floor": 26,
            "no_pallet": True,
        })
        assert r.status_code == 200
        assert r.get_json()["hi"] == 10   # floor(60/6)

    def test_custom_double_stack(self, client):
        r = self._post(client, {
            "length": 12, "width": 8, "height": 6,
            "retailer_id": "custom",
            "max_height": 60,
            "double_stack_allowed": True,
            "max_pallets_per_floor": 26,
            "no_pallet": False,
            "case_pack_qty": 1,
        })
        d = r.get_json()
        assert d["stack_multiplier"] == 2
        assert d["truckload_qty"] == d["total"] * 26 * 2

    def test_custom_defaults_when_params_omitted(self, client):
        """Custom retailer falls back to sensible defaults if params missing."""
        r = self._post(client, {"length": 12, "width": 8, "height": 6,
                                "retailer_id": "custom"})
        assert r.status_code == 200


# ── Bulk calculate ────────────────────────────────────────────

class TestBulkCalculate:
    def _post(self, client, body):
        return client.post("/api/calculate-bulk",
                           data=json.dumps(body),
                           content_type="application/json")

    def test_basic_bulk(self, client):
        r = self._post(client, {
            "retailer_id": 1,
            "cases": [
                {"sku": "A", "length": 12, "width": 8, "height": 6, "case_pack_qty": 1},
                {"sku": "B", "length": 10, "width": 10, "height": 8, "case_pack_qty": 2},
            ],
        })
        assert r.status_code == 200
        rows = r.get_json()
        assert len(rows) == 2
        assert rows[0]["sku"] == "A"
        assert rows[0]["ti"] == 20
        assert rows[1]["sku"] == "B"

    def test_bulk_empty_cases(self, client):
        r = self._post(client, {"retailer_id": 1, "cases": []})
        assert r.status_code == 400

    def test_bulk_unknown_retailer(self, client):
        r = self._post(client, {"retailer_id": 9999, "cases": [
            {"length": 12, "width": 8, "height": 6}
        ]})
        assert r.status_code == 404

    def test_bulk_skips_invalid_rows(self, client):
        r = self._post(client, {
            "retailer_id": 1,
            "cases": [
                {"sku": "good", "length": 12, "width": 8, "height": 6},
                {"sku": "bad",  "length": -1, "width": 8, "height": 6},
                {"sku": "also-bad"},
            ],
        })
        assert r.status_code == 200
        assert len(r.get_json()) == 1

    def test_bulk_custom_retailer(self, client):
        r = self._post(client, {
            "retailer_id": "custom",
            "max_height": 50,
            "double_stack_allowed": False,
            "max_pallets_per_floor": 20,
            "no_pallet": False,
            "cases": [{"sku": "X", "length": 12, "width": 8, "height": 6}],
        })
        assert r.status_code == 200
        d = r.get_json()[0]
        assert d["hi"] == 7     # floor((50-5.5)/6) = 7
        assert d["max_pallets_per_floor"] == 20

    def test_bulk_per_row_case_pack(self, client):
        r = self._post(client, {
            "retailer_id": 1,
            "cases": [
                {"sku": "A", "length": 12, "width": 8, "height": 6, "case_pack_qty": 6},
            ],
        })
        d = r.get_json()[0]
        assert d["case_pack_qty"] == 6
        assert d["truckload_qty"] == 6 * d["total"] * 26


# ── Shoppable API validation ──────────────────────────────────

SAMS_ID = "8"   # Sam's Club — is_club_store=True, chimney_allowed=True
BJS_ID  = "15"  # BJ's Wholesale — is_club_store=True, chimney_allowed=False
AMAZON_ID = "4" # Amazon — is_club_store=False
VALID_DIMS = {"length": 10, "width": 8, "height": 6, "retailer_id": SAMS_ID}

class TestShoppableAPI:
    def test_shoppable_rejected_for_non_club_store(self, client):
        body = {**VALID_DIMS, "retailer_id": AMAZON_ID,
                "shoppable": {"sides": 4}}
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
                "shoppable": {"sides": 4}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400

    def test_shoppable_rejected_with_invalid_sides_value(self, client):
        body = {**VALID_DIMS, "shoppable": {"sides": 1}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 400
        assert 'sides' in r.get_json()['error'].lower()

    def test_shoppable_accepted_for_club_store(self, client):
        body = {**VALID_DIMS, "shoppable": {"sides": 3}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 200
        data = r.get_json()
        assert 'shoppable' in data

    def test_shoppable_response_shape(self, client):
        body = {**VALID_DIMS,
                "shoppable": {"sides": 3,
                              "max_empty_pct": 0.15,
                              "rounding_gaps": True}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 200
        d = r.get_json()
        assert 'total' in d
        s = d['shoppable']
        assert isinstance(s['ti'], int)
        assert s['mode'] in ('pure_facing', 'filled', 'partial', 'standard', 'shoppable_spiral')
        assert 0.0 <= s['void_pct'] <= 1.0
        assert 'error' in s

    def test_shoppable_ti_lte_standard_ti(self, client):
        body = {**VALID_DIMS, "shoppable": {"sides": 4}}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        d = r.get_json()
        assert d['shoppable']['ti'] <= d['total']

    def test_shoppable_pod_dimensions_13x7(self, client):
        # Regression: 13.5×7.4 with 4 shoppable sides was reporting 47.9"×37"
        # (standard grid dims) instead of 43.1"×35.7" (shoppable arrangement dims).
        body = {
            "length": 13.5, "width": 7.4, "height": 6,
            "retailer_id": SAMS_ID,
            "shoppable": {"sides": 4},
        }
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        d = r.get_json()
        assert d['pod_length'] == pytest.approx(43.1, abs=0.05)
        assert d['pod_width']  == pytest.approx(35.7, abs=0.05)

    def test_no_shoppable_key_without_block(self, client):
        body = {**VALID_DIMS}
        r = client.post('/api/calculate',
                        data=json.dumps(body),
                        content_type='application/json')
        assert r.status_code == 200
        assert 'shoppable' not in r.get_json()
