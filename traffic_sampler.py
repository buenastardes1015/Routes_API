#!/usr/bin/env python3
"""
traffic_sampler.py
Polls the Google Maps Routes API for live travel time from
Toowong Village to Greenmount Beach and appends results to a CSV.

Schedule this via Windows Task Scheduler to run every 15 minutes, 5am-9pm.
"""

import csv
import os
import sys
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# CONFIG
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

ORIGIN = "-27.484951283500536, 152.98755926031623"  # Toowong Village Parking
DESTINATION = "-28.1674358635075, 153.54325398418715"  # Greenmount Beach, QLD

OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_log.csv")
TIMEZONE = os.environ.get("TRAFFIC_TIMEZONE", "Australia/Brisbane")
LOCAL_TZ = ZoneInfo(TIMEZONE)

ROUTES = [
    {
        "direction": "Southbound",
        "origin": ORIGIN,
        "destination": DESTINATION,
        "origin_label": "Toowong Village",
        "destination_label": "Greenmount Beach",
    },
    {
        "direction": "Northbound",
        "origin": DESTINATION,
        "destination": ORIGIN,
        "origin_label": "Greenmount Beach",
        "destination_label": "Toowong Village",
    },
]

# Hours to allow polling (script will exit silently outside these hours)
# Windows Task Scheduler will call this every 15 min; the script self-limits.
START_HOUR = 5  # 5am
END_HOUR = 21  # 9pm (runs up to and including 8:59am/pm)

CSV_FIELDS = [
    "sample_timestamp",
    "sample_batch_id",
    "direction",
    "origin_label",
    "destination_label",
    "day_of_week",
    "date",
    "hour",
    "minute",
    "timezone",
    "duration_traffic_min",
    "duration_static_min",
    "delay_min",
    "delay_ratio",
    "distance_km",
    "route_description",
]


def is_within_hours():
    hour = datetime.now(LOCAL_TZ).hour
    return START_HOUR <= hour < END_HOUR


def format_hm(total_seconds: int) -> str:
    """Format a duration in seconds as 'Xh Ym' (or 'Ym' if under an hour)."""
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(int(round(total_seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{sign}{hours}h {minutes}m"
    return f"{sign}{minutes}m"


def build_lat_lng(lat_lng: str) -> dict:
    latitude_str, longitude_str = lat_lng.split(",")
    return {
        "latitude": float(latitude_str),
        "longitude": float(longitude_str),
    }


def get_travel_time(route_config, api_key, sample_timestamp, sample_batch_id):
    """
    Calls the Routes API (Compute Routes) with TRAFFIC_AWARE_OPTIMAL.
    Returns a dict of the result, or raises on failure.
    """
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,"
            "routes.staticDuration,"
            "routes.distanceMeters,"
            "routes.description"
        ),
    }

    body = {
        "origin": {"location": {"latLng": build_lat_lng(route_config["origin"])}},
        "destination": {"location": {"latLng": build_lat_lng(route_config["destination"])}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "computeAlternativeRoutes": False,
        "units": "METRIC",
    }

    response = requests.post(url, headers=headers, json=body, timeout=15)
    response.raise_for_status()
    data = response.json()

    if "routes" not in data or not data["routes"]:
        raise ValueError(f"No routes returned. Response: {data}")

    route = data["routes"][0]
    duration_traffic_s = int(route["duration"].replace("s", ""))
    duration_static_s = int(route["staticDuration"].replace("s", ""))
    distance_m = route.get("distanceMeters", 0)
    route_description = route.get("description", "")

    delay_s = duration_traffic_s - duration_static_s
    delay_ratio = delay_s / duration_static_s if duration_static_s else 0.0

    return {
        "sample_timestamp": sample_timestamp.isoformat(timespec="seconds"),
        "sample_batch_id": sample_batch_id,
        "direction": route_config["direction"],
        "origin_label": route_config["origin_label"],
        "destination_label": route_config["destination_label"],
        "day_of_week": sample_timestamp.strftime("%A"),
        "date": sample_timestamp.strftime("%Y-%m-%d"),
        "hour": sample_timestamp.hour,
        "minute": sample_timestamp.minute,
        "timezone": TIMEZONE,
        "duration_traffic_min": round(duration_traffic_s / 60, 1),
        "duration_static_min": round(duration_static_s / 60, 1),
        "delay_min": round(delay_s / 60, 1),
        "delay_ratio": round(delay_ratio, 3),
        "distance_km": round(distance_m / 1000, 2),
        "route_description": route_description,
        "_duration_traffic_s": duration_traffic_s,
        "_delay_s": delay_s,
    }


def append_to_csv(row: dict, filepath: str):
    file_exists = os.path.isfile(filepath)
    with open(filepath, "a", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def migrate_csv_if_needed(filepath: str):
    if not os.path.isfile(filepath):
        return

    with open(filepath, newline="", encoding="utf-8") as file_handle:
        reader = csv.DictReader(file_handle)
        existing_fields = reader.fieldnames or []
        if existing_fields == CSV_FIELDS:
            return
        rows = list(reader)

    for row in rows:
        timestamp = row.get("sample_timestamp") or row.get("timestamp") or ""
        direction = row.get("direction") or "Southbound"
        legacy_batch_id = timestamp[:16] if timestamp else "legacy"
        row["sample_timestamp"] = timestamp
        row["sample_batch_id"] = row.get("sample_batch_id") or legacy_batch_id
        row["direction"] = direction
        row["origin_label"] = row.get("origin_label") or (
            "Toowong Village" if direction == "Southbound" else "Greenmount Beach"
        )
        row["destination_label"] = row.get("destination_label") or (
            "Greenmount Beach" if direction == "Southbound" else "Toowong Village"
        )
        row["timezone"] = row.get("timezone") or TIMEZONE
        row["route_description"] = row.get("route_description") or ""

    with open(filepath, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    if not is_within_hours():
        sys.exit(0)

    if not API_KEY:
        print("ERROR: GOOGLE_MAPS_API_KEY not set. Add it to .env.", file=sys.stderr)
        sys.exit(1)

    try:
        migrate_csv_if_needed(OUTPUT_CSV)
        sample_timestamp = datetime.now(LOCAL_TZ)
        sample_batch_id = f"{sample_timestamp.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"

        for route in ROUTES:
            result = get_travel_time(route, API_KEY, sample_timestamp, sample_batch_id)
            append_to_csv(result, OUTPUT_CSV)
            print(
                f"[{result['sample_timestamp']}] "
                f"{result['direction']} "
                f"{format_hm(result['_duration_traffic_s'])} "
                f"(+{format_hm(result['_delay_s'])} vs no traffic) "
                f"| {result['distance_km']} km"
            )
    except Exception as exc:
        error_log = OUTPUT_CSV.replace("traffic_log.csv", "traffic_errors.log")
        with open(error_log, "a", encoding="utf-8") as file_handle:
            file_handle.write(f"[{datetime.now(LOCAL_TZ).isoformat()}] ERROR: {exc}\n")
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
