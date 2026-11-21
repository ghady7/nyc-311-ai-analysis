import duckdb

con = duckdb.connect()
raw = con.execute("SELECT count(*) FROM read_json_auto('data/raw/raw_311_20261118_203000.json.gz')").fetchone()[0]
clean = con.execute("SELECT count(*) FROM read_parquet('data/clean/clean_complaints.parquet')").fetchone()[0]
quar = con.execute("SELECT count(*) FROM read_parquet('data/quarantine/quarantine_complaints.parquet')").fetchone()[0]

print(f"RAW_COUNT={raw}")
print(f"CLEAN_COUNT={clean}")
print(f"QUARANTINE_COUNT={quar}")
print(f"SUM={clean + quar}")
print(f"DELTA={raw - (clean + quar)}")
