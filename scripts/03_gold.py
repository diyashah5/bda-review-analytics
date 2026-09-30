"""Gold layer: build small analysis tables (CSV) for the dashboard and report.
Run from the repo root:  python scripts/03_gold.py
Needs:  data/silver  (created by 02_silver.py)
"""
import os
from pyspark.sql import SparkSession, Window, functions as F
from pyspark.ml.feature import StopWordsRemover

spark = (SparkSession.builder.appName("gold")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.sql.execution.arrow.pyspark.enabled", "false")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
os.makedirs("data/gold", exist_ok=True)

silver = spark.read.parquet("data/silver")
silver.createOrReplaceTempView("reviews")


def save(df, name):
    pdf = df.toPandas()
    pdf.to_csv(f"data/gold/{name}.csv", index=False)
    print(f"saved data/gold/{name}.csv  ({len(pdf):,} rows)")


# 1. Small "cube": every dashboard chart and filter is built from this table.
cube = spark.sql("""
    SELECT category, price_band, rating, sentiment,
           COUNT(*)                AS reviews,
           ROUND(SUM(price), 0)    AS sum_price,
           SUM(word_count)         AS sum_words
    FROM reviews
    GROUP BY category, price_band, rating, sentiment
    ORDER BY category, price_band, rating
""")
save(cube, "cube")

# 2. Products with at least 100 reviews
products = spark.sql("""
    SELECT product_name, category,
           COUNT(*)                                                   AS reviews,
           ROUND(AVG(rating), 2)                                      AS avg_rating,
           ROUND(100 * AVG(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END), 1) AS pct_positive,
           ROUND(100 * AVG(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END), 1) AS pct_negative,
           ROUND(AVG(price), 0)                                       AS avg_price
    FROM reviews
    GROUP BY product_name, category
    HAVING COUNT(*) >= 100
    ORDER BY reviews DESC
""")
save(products, "products")

# 3. Most common words per sentiment (stop words removed)
tokens = silver.select("sentiment", F.split("review_text", " ").alias("raw_words"))
remover = StopWordsRemover(inputCol="raw_words", outputCol="words")
words = (remover.transform(tokens)
         .select("sentiment", F.explode("words").alias("word"))
         .filter(F.length("word") > 2))
counts = words.groupBy("sentiment", "word").count()

rank = Window.partitionBy("sentiment").orderBy(F.desc("count"))
top_words = (counts.withColumn("rank", F.row_number().over(rank))
             .filter("rank <= 25")
             .select("sentiment", "word", "count")
             .orderBy("sentiment", F.desc("count")))
save(top_words, "top_words")

# 4. Words that lean positive or negative (share of the word's uses per sentiment)
signals = (counts.groupBy("word")
           .pivot("sentiment", ["negative", "neutral", "positive"]).sum("count")
           .fillna(0))
signals = (signals
           .withColumn("total", F.col("negative") + F.col("neutral") + F.col("positive"))
           .filter("total >= 300")
           .withColumn("neg_share", F.round(F.col("negative") / F.col("total"), 3))
           .withColumn("pos_share", F.round(F.col("positive") / F.col("total"), 3))
           .orderBy(F.desc("total")))
save(signals, "word_signals")

print("\nGold layer done. Files are in data/gold/")
spark.stop()
