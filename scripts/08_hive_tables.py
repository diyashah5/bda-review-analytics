"""Hive tables: store the Silver data as Hive-metastore tables and query them with Spark SQL.
Run from the repo root:  python scripts/08_hive_tables.py
Needs:  data/silver (from 02_silver.py)

This uses Spark's built-in Hive support (local Derby metastore, Parquet files in
spark-warehouse/). It is Hive tables + HiveQL-style queries on ONE machine,
not a Hadoop cluster and not HDFS.
"""
from pyspark.sql import SparkSession

spark = (SparkSession.builder.appName("hive-tables")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.sql.warehouse.dir", "spark-warehouse")
         .enableHiveSupport()
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
print("Catalog in use:", spark.conf.get("spark.sql.catalogImplementation"))

spark.sql("CREATE DATABASE IF NOT EXISTS review_db")
spark.sql("USE review_db")
spark.sql("DROP TABLE IF EXISTS reviews")

silver = spark.read.parquet("data/silver")
(silver.select("product_name", "price", "price_band", "rating", "sentiment",
               "word_count", "review_text", "category")
       .write.mode("overwrite")
       .partitionBy("category")               # Hive-style partitions: one folder per category
       .format("parquet")
       .saveAsTable("reviews"))

print("\nTables in review_db:")
spark.sql("SHOW TABLES").show(truncate=False)
print("Partitions of review_db.reviews:")
spark.sql("SHOW PARTITIONS reviews").show(truncate=False)
print("Table structure:")
spark.sql("DESCRIBE reviews").show(truncate=False)

print("Query 1: sentiment share by category")
spark.sql("""
    SELECT category, COUNT(*) AS reviews,
           ROUND(AVG(rating), 2) AS avg_rating,
           ROUND(100 * AVG(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END), 1) AS pct_positive,
           ROUND(100 * AVG(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END), 1) AS pct_negative
    FROM reviews
    GROUP BY category
    ORDER BY reviews DESC
""").show(truncate=False)

print("Query 2: rating and sentiment by price band")
spark.sql("""
    SELECT price_band, COUNT(*) AS reviews, ROUND(AVG(rating), 2) AS avg_rating,
           ROUND(100 * AVG(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END), 1) AS pct_positive
    FROM reviews
    GROUP BY price_band
    ORDER BY price_band
""").show(truncate=False)

print("Query 3: 10 most reviewed products")
spark.sql("""
    SELECT product_name, category, COUNT(*) AS reviews, ROUND(AVG(rating), 2) AS avg_rating
    FROM reviews
    GROUP BY product_name, category
    ORDER BY reviews DESC
    LIMIT 10
""").show(truncate=60)

print("Query 4: partition pruning (only the Appliances partition is read)")
spark.sql("SELECT COUNT(*) AS appliance_reviews FROM reviews WHERE category = 'Appliances'").show()

spark.stop()
print("Hive tables ready in database review_db.")
