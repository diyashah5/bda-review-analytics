"""Speed test: Pandas vs Spark on the same job, at two data sizes.
Run from the repo root:  python scripts/07_benchmark.py      (takes a few minutes)

Job: read the Silver Parquet columns, repeat the data N times, then group by
category and price band and compute the review count and average rating.
"""
import os
import statistics
import time

import pandas as pd
from pyspark.sql import SparkSession, functions as F

COLS = ["category", "price_band", "rating"]
SCALES = [1, 20]          # 1x = the real data, 20x = the same data repeated 20 times
RUNS = 3                  # each test is run 3 times; the median time is reported
rows_1x = len(pd.read_parquet("data/silver", columns=["rating"]))


def run_pandas(scale):
    t = time.perf_counter()
    df = pd.read_parquet("data/silver", columns=COLS)
    if scale > 1:
        df = pd.concat([df] * scale, ignore_index=True)
    df.groupby(["category", "price_band"]).agg(
        reviews=("rating", "size"), avg_rating=("rating", "mean"))
    return time.perf_counter() - t


def spark_session(cores):
    return (SparkSession.builder.appName("benchmark")
            .master(f"local[{cores}]")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate())


def run_spark(spark, scale):
    t = time.perf_counter()
    df = spark.read.parquet("data/silver").select(*COLS)
    if scale > 1:
        df = df.crossJoin(spark.range(scale).drop("id"))
    df.groupBy("category", "price_band").agg(
        F.count("*").alias("reviews"), F.avg("rating").alias("avg_rating")).collect()
    return time.perf_counter() - t


results = []
for scale in SCALES:
    times = [run_pandas(scale) for _ in range(RUNS)]
    results.append({"engine": "Pandas", "rows": rows_1x * scale,
                    "seconds": round(statistics.median(times), 2)})

cpu = os.cpu_count() or 1
for cores in sorted({1, min(2, cpu), cpu}):
    spark = spark_session(cores)
    spark.sparkContext.setLogLevel("ERROR")
    run_spark(spark, 1)                       # warm-up run, not counted
    for scale in SCALES:
        times = [run_spark(spark, scale) for _ in range(RUNS)]
        results.append({"engine": f"Spark ({cores} core{'s' if cores > 1 else ''})",
                        "rows": rows_1x * scale,
                        "seconds": round(statistics.median(times), 2)})
    spark.stop()

out = pd.DataFrame(results)
os.makedirs("data/gold", exist_ok=True)
out.to_csv("data/gold/benchmark.csv", index=False)
print(out.to_string(index=False))
print("\nSaved data/gold/benchmark.csv")
