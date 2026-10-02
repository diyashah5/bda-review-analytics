"""Warehouse: build a star schema with Spark and load it into PostgreSQL.
Run from the repo root:  python scripts/05_warehouse.py
Needs:  data/silver (from 02_silver.py), data/gold (from 03/04) and a running PostgreSQL
        (docker compose up -d   -- see README).
"""
import io
import os
import sys

import pandas as pd
import psycopg2
from pyspark.sql import SparkSession, Window, functions as F

DB = dict(host=os.getenv("PGHOST", "localhost"),
          port=int(os.getenv("PGPORT", "5432")),
          user=os.getenv("PGUSER", "bda"),
          password=os.getenv("PGPASSWORD", "bda123"),
          dbname=os.getenv("PGDATABASE", "reviews"))

# ---- connect first, so a missing database fails fast with a clear message ----
try:
    conn = psycopg2.connect(**DB)
except psycopg2.OperationalError as e:
    sys.exit("Could not connect to PostgreSQL. Start it first (see README: "
             "'docker compose up -d').\n" + str(e))
conn.autocommit = True
cur = conn.cursor()

spark = (SparkSession.builder.appName("warehouse")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.sql.execution.arrow.pyspark.enabled", "false")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

silver = spark.read.parquet("data/silver")

# ---------------- build the dimensions and the fact table with Spark ----------------
dim_category = (silver.select(F.col("category").alias("category_name")).distinct()
                .withColumn("category_key", F.dense_rank().over(Window.orderBy("category_name")))
                .select("category_key", "category_name"))

dim_product = (silver.select("product_name", F.col("category").alias("category_name")).distinct()
               .join(dim_category, "category_name")
               .withColumn("product_key", F.row_number().over(Window.orderBy("product_name")))
               .select("product_key", "product_name", "category_key"))

dim_price_band = (silver.select("price_band").distinct()
                  .withColumn("price_band_key", F.dense_rank().over(Window.orderBy("price_band")))
                  .select("price_band_key", "price_band"))

dim_sentiment = spark.createDataFrame(
    [(1, "negative"), (2, "neutral"), (3, "positive")], ["sentiment_key", "sentiment"])

product_lookup = (dim_product.join(dim_category, "category_key")
                  .select("product_key", "product_name", "category_name"))

fact_reviews = (silver
                .withColumnRenamed("category", "category_name")
                .join(product_lookup, ["product_name", "category_name"])
                .join(dim_price_band, "price_band")
                .join(dim_sentiment, "sentiment")
                .withColumn("review_key", F.monotonically_increasing_id() + 1)
                .select("review_key", "product_key", "price_band_key", "sentiment_key",
                        F.col("rating").cast("int").alias("rating"),
                        F.round("price", 2).alias("price"),
                        F.col("word_count").cast("int").alias("word_count"),
                        "review_text"))

# ---------------- create the tables, then load them ----------------
cur.execute(open("sql/schema.sql").read())


def copy_df(table, pdf):
    buf = io.StringIO()
    pdf.to_csv(buf, index=False, header=False)
    buf.seek(0)
    cols = ", ".join(pdf.columns)
    cur.copy_expert(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv)", buf)
    print(f"loaded {table:<18}{len(pdf):>9,} rows")


for name, sdf in [("dim_category", dim_category), ("dim_product", dim_product),
                  ("dim_price_band", dim_price_band), ("dim_sentiment", dim_sentiment),
                  ("fact_reviews", fact_reviews)]:
    copy_df(name, sdf.toPandas())

# ---------------- also load the Gold tables (small CSV files) ----------------
SQL_TYPES = {"int64": "BIGINT", "float64": "DOUBLE PRECISION"}
skip = {"model_weights"}                      # 20,000-row model file, not needed in SQL
for fname in sorted(os.listdir("data/gold")):
    if not fname.endswith(".csv") or fname[:-4] in skip:
        continue
    table = "gold_" + fname[:-4]
    pdf = pd.read_csv(f"data/gold/{fname}")
    cols_sql = ", ".join(f'"{c}" {SQL_TYPES.get(str(t), "TEXT")}' for c, t in pdf.dtypes.items())
    cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.execute(f"CREATE TABLE {table} ({cols_sql})")
    buf = io.StringIO()
    pdf.to_csv(buf, index=False, header=False)
    buf.seek(0)
    cur.copy_expert(f"COPY {table} FROM STDIN WITH (FORMAT csv)", buf)
    print(f"loaded {table:<26}{len(pdf):>6,} rows")

# ---------------- quick integrity check ----------------
cur.execute("""
    SELECT (SELECT COUNT(*) FROM fact_reviews)                      AS fact_rows,
           (SELECT COUNT(*) FROM fact_reviews f
              JOIN dim_product p ON f.product_key = p.product_key)  AS rows_with_product""")
fact_rows, joined = cur.fetchone()
print(f"\nCheck: {fact_rows:,} fact rows, {joined:,} match a product "
      f"-> {'OK' if fact_rows == joined else 'MISMATCH'}")
print("Warehouse ready. Run: python scripts/06_sql_report.py")
conn.close()
spark.stop()
