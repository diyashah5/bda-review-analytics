"""Run the SQL analysis queries on the warehouse and save the results for the report.
Run from the repo root:  python scripts/06_sql_report.py
"""
import os
import re
import sys

import pandas as pd
import psycopg2

DB = dict(host=os.getenv("PGHOST", "localhost"),
          port=int(os.getenv("PGPORT", "5432")),
          user=os.getenv("PGUSER", "bda"),
          password=os.getenv("PGPASSWORD", "bda123"),
          dbname=os.getenv("PGDATABASE", "reviews"))
try:
    conn = psycopg2.connect(**DB)
except psycopg2.OperationalError as e:
    sys.exit("Could not connect to PostgreSQL. Run 05_warehouse.py first.\n" + str(e))

text = open("sql/analysis_queries.sql").read()
blocks = re.split(r"^-- name:\s*", text, flags=re.M)[1:]

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 70)
lines = []
for block in blocks:
    title, _, query = block.partition("\n")
    result = pd.read_sql_query(query.strip().rstrip(";"), conn)
    section = f"=== {title.strip()} ===\n{result.to_string(index=False)}\n"
    print(section)
    lines.append(section)

os.makedirs("docs", exist_ok=True)
with open("docs/sql_results.txt", "w") as f:
    f.write("\n".join(lines))
print("Saved docs/sql_results.txt")
conn.close()
