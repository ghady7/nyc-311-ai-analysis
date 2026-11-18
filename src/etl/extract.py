"""
NYC 311 Service Requests Extraction Engine
Extracts rolling service request data from NYC Open Data (Socrata API)
and saves immutable compressed JSON lines artifacts to data/raw/.
"""

import os
import sys
import json
import gzip
import time
import argparse
import subprocess
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

SOCRATA_ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
DEFAULT_ROLLING_DAYS = 30
DEFAULT_MAX_RECORDS = 100000
BATCH_SIZE = 25000
MAX_RETRIES = 5
BACKOFF_FACTOR = 2


def load_env_file():
    """Simple parser for .env if python-dotenv is not yet installed."""
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key and val and key not in os.environ:
                        os.environ[key] = val


load_env_file()


def fetch_batch(cutoff_iso: str, offset: int, limit: int, app_token: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch a single paginated batch using curl.exe or requests with exponential backoff."""
    params = {
        "$where": f"created_date >= '{cutoff_iso}'",
        "$order": "created_date DESC",
        "$limit": str(limit),
        "$offset": str(offset)
    }
    query_str = urllib.parse.urlencode(params)
    url = f"{SOCRATA_ENDPOINT}?{query_str}"
    
    # Try requests first if available
    try:
        import requests
        headers = {"Accept": "application/json", "User-Agent": "nyc-311-analytics-pipeline/1.0"}
        if app_token:
            headers["X-App-Token"] = app_token
            
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                res = requests.get(url, headers=headers, timeout=60)
                if res.status_code == 200:
                    return res.json()
                elif res.status_code == 429:
                    wait_time = BACKOFF_FACTOR ** attempt
                    time.sleep(wait_time)
                else:
                    res.raise_for_status()
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(BACKOFF_FACTOR ** attempt)
    except ImportError:
        # Fallback to curl.exe
        cmd = ["curl.exe", "-s", "-f"]
        if app_token:
            cmd.extend(["-H", f"X-App-Token: {app_token}"])
        cmd.append(url)
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=90)
                data = json.loads(proc.stdout)
                return data
            except Exception as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"curl.exe fetch failed at offset {offset}: {exc}")
                time.sleep(BACKOFF_FACTOR ** attempt)
                
    return []


def extract_311(rolling_days: int = DEFAULT_ROLLING_DAYS, max_records: Optional[int] = DEFAULT_MAX_RECORDS) -> str:
    """
    Extract NYC 311 requests for the past `rolling_days` and write to compressed .json.gz.
    Returns the absolute path of the generated raw file.
    """
    start_time = time.time()
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=rolling_days)
    cutoff_iso = cutoff_dt.strftime("%Y-%m-%dT00:00:00.000")
    
    print("=" * 60)
    print("NYC 311 EXTRACTION ENGINE")
    print(f"Extraction Window: {cutoff_iso} to {now_utc.isoformat()}")
    print(f"Rolling Days:      {rolling_days}")
    print(f"Target Record Cap: {max_records:,}" if max_records else "Target Record Cap: Unlimited")
    print("=" * 60)

    app_token = os.getenv("NYC_APP_TOKEN")
    if app_token and app_token.strip():
        print(f"Auth: Authenticated (App Token loaded)")
        token_val = app_token.strip()
    else:
        print(f"Auth: Anonymous (Subject to Socrata public rate limits)")
        token_val = None

    raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))
    os.makedirs(raw_dir, exist_ok=True)
    
    timestamp_str = now_utc.strftime("%Y%m%d_%H%M%S")
    out_filename = f"raw_311_{timestamp_str}.json.gz"
    out_path = os.path.join(raw_dir, out_filename)
    
    total_records = 0
    offset = 0
    
    print(f"\nWriting raw records to: {out_path}")
    with gzip.open(out_path, "wt", encoding="utf-8") as gz_file:
        while True:
            limit = BATCH_SIZE
            if max_records and (total_records + limit > max_records):
                limit = max_records - total_records
                if limit <= 0:
                    break
                    
            print(f"Pulling batch: offset={offset:,}, limit={limit:,} ...")
            batch = fetch_batch(cutoff_iso, offset, limit, token_val)
            batch_count = len(batch)
            
            if batch_count == 0:
                print("No more records returned from API.")
                break
                
            for record in batch:
                gz_file.write(json.dumps(record) + "\n")
                
            total_records += batch_count
            offset += batch_count
            print(f"-> Cumulative downloaded: {total_records:,} records")
            
            if batch_count < limit or (max_records and total_records >= max_records):
                break

    elapsed = time.time() - start_time
    file_size_mb = os.path.getsize(out_path) / (1024 * 1024)
    
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print(f"Total Rows Extracted: {total_records:,}")
    print(f"Compressed File Size: {file_size_mb:.2f} MB")
    print(f"Total Elapsed Time:   {elapsed:.1f}s")
    print(f"Raw Artifact:         {out_path}")
    print("=" * 60)
    
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract rolling NYC 311 data from Socrata API.")
    parser.add_argument("--days", type=int, default=DEFAULT_ROLLING_DAYS, help="Rolling window in days (default: 30)")
    parser.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS, help="Cap records (default: 100,000)")
    args = parser.parse_args()
    
    extract_311(rolling_days=args.days, max_records=args.max_records)
