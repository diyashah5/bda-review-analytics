"""Silver layer: clean the Bronze data and add analysis columns.
Run from the repo root:  python scripts/02_silver.py
"""
import pandas as pd
from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder.appName("silver")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

report = []                                   # rows for the before/after table

def log(step, df):
    n = df.count()
    report.append({"step": step, "rows": n})
    print(f"{step:<48}{n:>10,}")
    return df

df = log("1. Bronze rows (raw)", spark.read.parquet("data/bronze"))

# 2. exact duplicate rows
df = log("2. After removing exact duplicates", df.dropDuplicates())

# 3. rating must be a whole number from 1 to 5 (drops shifted / broken rows)
df = df.withColumn("rate_int", F.expr("try_cast(rate as int)"))
df = log("3. After removing invalid ratings",
         df.filter(F.col("rate_int").between(1, 5)))

# 4. price: keep digits only ("?3,999" with broken symbol -> 3999)
df = df.withColumn("price_clean", F.regexp_replace("price", r"[^0-9.]", ""))
df = df.withColumn("price_num", F.expr("try_cast(price_clean as double)"))
df = log("4. After removing rows with unreadable price",
         df.filter(F.col("price_num").isNotNull() & (F.col("price_num") > 0)))

# 5. review text: lowercase, letters only, single spaces
df = df.withColumn(
    "review_text",
    F.trim(F.regexp_replace(
        F.regexp_replace(F.lower(F.coalesce(F.col("summary"), F.lit(""))),
                         r"[^a-z\s]", " "),
        r"\s+", " ")))
df = log("5. After removing empty review text",
         df.filter(F.length("review_text") >= 2))

# 6. tidy columns
df = (df
      .withColumn("product_name",
                  F.trim(F.regexp_replace(
                      F.regexp_replace("product_name", r"[?\uFFFD\u00a0]{2,}", " "),
                      r"\s+", " ")))
      .withColumn("review_title",
                  F.when(F.col("review_title") == "Nan", None)
                   .otherwise(F.col("review_title"))))

# 7. new analysis columns
name = F.lower(F.col("product_name"))
df = (df
      .withColumn("rating", F.col("rate_int"))
      .withColumn("price", F.col("price_num"))
      .withColumn("sentiment",
                  F.when(F.col("rating") >= 4, "positive")
                   .when(F.col("rating") == 3, "neutral")
                   .otherwise("negative"))
      .withColumn("word_count", F.size(F.split("review_text", " ")))
      .withColumn("price_band",
                  F.when(F.col("price") < 500, "1. Under 500")
                   .when(F.col("price") < 1000, "2. 500-999")
                   .when(F.col("price") < 3000, "3. 1,000-2,999")
                   .when(F.col("price") < 10000, "4. 3,000-9,999")
                   .otherwise("5. 10,000+"))
      .withColumn(
          "category",
          F.when(name.rlike(r"wall clock|bedsheet|bed sheet|curtain|cushion|showpiece|pillow|blanket|carpet|doormat"), "Home Decor & Furnishing")
           .when(name.rlike(r"football|cricket|gym|bicycle|\bcycle\b|yoga|dumbbell|badminton|abdomen|fitness|skipping"), "Sports & Fitness")
           .when(name.rlike(r"\bmop\b|dettol|serum|face|shampoo|soap|lotion|cream|mamaearth|detergent|cleaner|cleaning|antiseptic|sanitizer|perfume|deodorant"), "Personal Care & Cleaning")
           .when(name.rlike(r"\btoy|toys|seed|plant|garden|puzzle|doll|remote control|\bcar\b"), "Toys & Garden")
           .when(name.rlike(r"\bfan\b|cooler|air conditioner|\bac\b|\biron\b|heater|geyser|washing|wash\b|refrigerator|vacuum|purifier|sewing|trimmer|shaver|dryer|chimney|inverter|\bups\b|food processor|stabili[sz]er|mixer|grinder|juicer|blender|oven|cooker|kettle|toaster|induction|chopper"), "Appliances")
           .when(name.rlike(r"dinner|flask|bottle|jar|\bpan\b|tawa|lunch|casserole|cookware|utensil|steel|opalware|glass|\bcup|mug|plate|bowl|kitchen"), "Kitchen & Dining")
           .when(name.rlike(r"bluetooth|speaker|headphone|earphone|earbud|neckband|\bled\b|\btv\b|smart|\bssd\b|hard disk|pen drive|memory card|laptop|mobile|phone|charger|cable|power bank|watch|\bband\b|mouse|keyboard|camera|router|printer|\bink\b|samsung|redmi|realme|poco|ipad|apple|chromecast|streaming|wifi|wi-fi|\bgb\b"), "Electronics & Accessories")
           .when(name.rlike(r"\bmen\b|women|shirt|jeans|shoe|sneaker|sandal|slipper|kurta|saree|jacket|\bcap\b|belt|wallet|\bbag\b|backpack|sunglass|cotton"), "Fashion & Apparel")
           .when(name.rlike(r"curtain|bedsheet|cushion|clock|lamp|shelf|rack|table|chair|sofa|\bbed\b|mattress|pillow|blanket|carpet|\bmat\b|frame|showpiece|stand|organi[sz]er|holder|door|wardrobe|light|home|wood|book"), "Home Decor & Furnishing")
           .otherwise("Other")))

silver = df.select("product_name", "category", "price", "price_band",
                   "rating", "sentiment", "review_title", "review_text", "word_count")
silver.write.mode("overwrite").parquet("data/silver")

# --- quick sanity output ---
s = spark.read.parquet("data/silver")
print("\nSilver rows:", f"{s.count():,}")
print("\nSentiment split:")
s.groupBy("sentiment").count().orderBy(F.desc("count")).show()
print("Category split:")
s.groupBy("category").count().orderBy(F.desc("count")).show()

# --- save the before/after table for the report ---
rep = pd.DataFrame(report)
rep["removed"] = rep["rows"].shift(1) - rep["rows"]
rep.to_csv("data/silver_quality_report.csv", index=False)
print(rep.to_string(index=False))
spark.stop()
