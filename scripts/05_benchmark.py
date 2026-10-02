"""Benchmark a representative Spark SQL aggregation at several partition counts."""
import os
import time
from pathlib import Path

import pandas as pd
from pyspark.sql import SparkSession


spark = (SparkSession.builder.appName("review-aggregation-benchmark")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

silver = spark.read.parquet("data/silver").select("category", "sentiment")
silver.cache()
row_count = silver.count()
repeats = max(1, int(os.getenv("BENCHMARK_REPEATS", "3")))
results = []

for partitions in (1, 4, 8):
    spark.conf.set("spark.sql.shuffle.partitions", str(partitions))
    # Warm the query path once so the recorded runs focus on the aggregation.
    silver.groupBy("category", "sentiment").count().collect()
    for run in range(1, repeats + 1):
        started = time.perf_counter()
        aggregates = silver.groupBy("category", "sentiment").count().collect()
        elapsed = time.perf_counter() - started
        results.append({
            "shuffle_partitions": partitions,
            "run": run,
            "input_rows": row_count,
            "aggregate_rows": len(aggregates),
            "runtime_seconds": round(elapsed, 4),
            "rows_per_second": round(row_count / elapsed, 2) if elapsed else 0,
        })

output = Path("data/benchmark/spark_aggregation.csv")
output.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(results).to_csv(output, index=False)
print(pd.DataFrame(results).to_string(index=False))
print(f"Benchmark results saved to {output}")

silver.unpersist()
spark.stop()