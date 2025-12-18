import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TRIPS_FILE = DATA_DIR / "trips.json"

IRS_RATES_URL = "https://www.irs.gov/tax-professionals/standard-mileage-rates"

# 2025 business rate: 70 cents per mile (0.70)
# Source: IRS Standard mileage rates page + Notice 2025-5
DEFAULT_IRS_BUSINESS_RATE = 0.70

ORS_API_KEY = os.environ.get("ORS_API_KEY")  # optional


def _read_trips():
    if not TRIPS_FILE.exists():
        return []
    try:
        return json.loads(TRIPS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _write_trips(trips):
    TRIPS_FILE.write_text(json.dumps(trips, indent=2), encoding="utf-8")


def _money(x: float) -> str:
    return f"${x:,.2f}"


def fetch_irs_business_rate() -> float:
    """
    Attempts to fetch the IRS business mileage rate by scraping the IRS page text.
    If it fails, returns DEFAULT_IRS_BUSINESS_RATE.
    """
    try:
        r = requests.get(IRS_RATES_URL, timeout=10)
        r.raise_for_status()
        text = re.sub(r"\s+", " ", r.text)

        # Common phrasing: "Self-employed and business: 70 cents/mile"
        m = re.search(r"Self-employed and business:\s*(\d+)\s*cents/mile", text, re.IGNORECASE)
        if m:
            cents = int(m.group(1))
            return cents / 100.0

        return DEFAULT_IRS_BUSINESS_RATE
    except Exception:
        return DEFAULT_IRS_BUSINESS_RATE


def geocode_ors(address: str):
    """
    OpenRouteService geocode (Pelias) without an SDK.
    NOTE: Requires ORS_API_KEY. If not present, return None.
    """
    if not ORS_API_KEY:
        return None

    url = "https://api.openrouteservice.org/geocode/search"
    headers = {"Authorization": ORS_API_KEY}
    params = {"text": address, "size": 1}
    resp = requests.get(url, headers=headers, params=params, timeout=12)
    resp.raise_for_status()
    data = resp.json()
    feats = data.get("features", [])
    if not feats:
        return None
    coords = feats[0]["geometry"]["coordinates"]  # [lon, lat]
    return coords


def driving_distance_miles_ors(start_addr: str, end_addr: str):
    """
    OpenRouteService directions distance in miles.
    Returns None if no key or geocoding fails.
    """
    if not ORS_API_KEY:
        return None

    start = geocode_ors(start_addr)
    end = geocode_ors(end_addr)
    if not start or not end:
        return None

    url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [start, end]}
    resp = requests.post(url, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    meters = resp.json()["features"][0]["properties"]["summary"]["distance"]
    miles = meters / 1609.344
    return miles


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


@app.route("/")
def index():
    trips = _read_trips()
    # Show newest first
    trips_sorted = sorted(trips, key=lambda t: t.get("created_at", ""), reverse=True)
    return render_template("index.html", trips=trips_sorted)


@app.route("/mileage", methods=["GET", "POST"])
def mileage():
    rate = fetch_irs_business_rate()

    if request.method == "POST":
        trip_type = request.form.get("trip_type", "one_way")  # one_way | roundtrip

        start_address = request.form.get("start_address", "").strip()
        end_address = request.form.get("end_address", "").strip()

        start_dt = request.form.get("start_datetime", "").strip()
        arrival_dt = request.form.get("arrival_datetime", "").strip()

        # Stops (up to 5 by default in the template)
        stops = []
        for i in range(1, 6):
            addr = request.form.get(f"stop_{i}_address", "").strip()
            dt = request.form.get(f"stop_{i}_datetime", "").strip()
            if addr or dt:
                stops.append({"address": addr, "datetime": dt})

        # Miles: allow manual entry, OR auto-calc if ORS key is present
        manual_one_way_miles = safe_float(request.form.get("manual_one_way_miles"))
        manual_stop_miles = safe_float(request.form.get("manual_stop_miles"))  # optional extra

        # Route legs if using ORS:
        computed_one_way = None
        computed_detail = []
        if ORS_API_KEY and start_address and end_address:
            # Build leg list: start -> stop1 -> stop2 -> ... -> end
            points = [start_address] + [s["address"] for s in stops if s.get("address")] + [end_address]
            if len(points) >= 2:
                total = 0.0
                ok = True
                for a, b in zip(points, points[1:]):
                    d = driving_distance_miles_ors(a, b)
                    if d is None:
                        ok = False
                        break
                    computed_detail.append({"from": a, "to": b, "miles": d})
                    total += d
                if ok:
                    computed_one_way = total

        one_way_miles = computed_one_way if computed_one_way is not None else manual_one_way_miles
        # Add optional "extra stop miles" if user wants to manually adjust
        one_way_miles = one_way_miles + manual_stop_miles

        if not start_address or not end_address:
            flash("Start and End address are required.", "danger")
            return redirect(url_for("mileage"))

        if one_way_miles <= 0:
            flash("Miles must be greater than 0 (enter manual miles or configure ORS_API_KEY).", "danger")
            return redirect(url_for("mileage"))

        if trip_type == "roundtrip":
            total_miles = one_way_miles * 2
        else:
            total_miles = one_way_miles

        reimbursement = total_miles * rate

        trip = {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "trip_type": trip_type,
            "start_address": start_address,
            "end_address": end_address,
            "start_datetime": start_dt,
            "arrival_datetime": arrival_dt,
            "stops": stops,
            "irs_business_rate": rate,
            "one_way_miles": round(one_way_miles, 2),
            "total_miles": round(total_miles, 2),
            "reimbursement": round(reimbursement, 2),
            "distance_source": "openrouteservice" if computed_one_way is not None else "manual",
            "distance_legs": computed_detail,
            "costs": {
                "gas": 0.0,
                "food": 0.0,
                "tolls": 0.0,
                "tickets": []
            }
        }

        trips = _read_trips()
        trips.append(trip)
        _write_trips(trips)

        flash("Trip saved.", "success")
        return redirect(url_for("index"))

    return render_template("mileage.html", irs_rate=rate, ors_enabled=bool(ORS_API_KEY))


@app.route("/costs", methods=["GET", "POST"])
def costs():
    trips = _read_trips()
    trips_sorted = sorted(trips, key=lambda t: t.get("created_at", ""), reverse=True)

    if request.method == "POST":
        created_at = request.form.get("created_at")
        gas = safe_float(request.form.get("gas"))
        food = safe_float(request.form.get("food"))
        tolls = safe_float(request.form.get("tolls"))

        # ticket fields (single ticket per submit; repeat to add more)
        t_state = request.form.get("ticket_state", "").strip()
        t_county = request.form.get("ticket_county", "").strip()
        t_dept = request.form.get("ticket_department", "").strip()
        t_officer = request.form.get("ticket_officer", "").strip()
        t_number = request.form.get("ticket_number", "").strip()

        updated = False
        for trip in trips:
            if trip.get("created_at") == created_at:
                trip["costs"]["gas"] = gas
                trip["costs"]["food"] = food
                trip["costs"]["tolls"] = tolls

                # Add ticket if ticket number present (or any field)
                if any([t_state, t_county, t_dept, t_officer, t_number]):
                    trip["costs"]["tickets"].append({
                        "state": t_state,
                        "county": t_county,
                        "department": t_dept,
                        "citing_officer": t_officer,
                        "ticket_number": t_number
                    })
                updated = True
                break

        if updated:
            _write_trips(trips)
            flash("Costs updated.", "success")
        else:
            flash("Trip not found.", "danger")

        return redirect(url_for("costs"))

    return render_template("costs.html", trips=trips_sorted, money=_money)


@app.route("/api/trips")
def api_trips():
    """Simple API endpoint returning the JSON data (for future React front-end)."""
    return {"trips": _read_trips()}


if __name__ == "__main__":
    # local dev
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
