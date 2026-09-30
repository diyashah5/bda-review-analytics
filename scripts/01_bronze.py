"""Bronze layer: read the raw CSV and save it as Parquet, with no cleaning.
Run from the repo root:  python scripts/01_bronze.py
"""
from pyspark.sql import SparkSession

spark = (SparkSession.builder.appName("bronze")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

raw = (spark.read
       .option("header", True)
       .option("quote", '"')
       .option("escape", '"')
       .csv("data/flipkart_product.csv"))      # everything stays as text on purpose

# snake_case names are safe for Parquet, Hive and SQL
names = {"ProductName": "product_name", "Price": "price", "Rate": "rate",
         "Review": "review_title", "Summary": "summary"}
for old, new in names.items():
    raw = raw.withColumnRenamed(old, new)

raw.write.mode("overwrite").parquet("data/bronze")

check = spark.read.parquet("data/bronze")
print("Bronze rows:", f"{check.count():,}")
check.printSchema()
spark.stop()
