"""MLlib sentiment model: TF-IDF + Logistic Regression on the review TEXT only.
Run from the repo root:  python scripts/04_model.py
Needs:  data/silver  (created by 02_silver.py)

Important: the short review title is NOT used, because it is closely tied to the
star rating and would make the accuracy look better than it really is.
"""
import json
import math
import os
import re

import pandas as pd
from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import CountVectorizer, IDF, StopWordsRemover, Tokenizer
from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder.appName("model")
         .master("local[*]")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.sql.execution.arrow.pyspark.enabled", "false")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
os.makedirs("data/gold", exist_ok=True)

CLASSES = ["negative", "neutral", "positive"]          # labels 0, 1, 2
silver = spark.read.parquet("data/silver").filter(F.length("review_text") > 0)


def train_and_test(data, label_expr):
    data = data.withColumn("label", label_expr).filter(F.col("label").isNotNull())
    train, test = data.randomSplit([0.8, 0.2], seed=42)

    # class weights so the many 5-star reviews do not dominate the model
    counts = {r["label"]: r["count"] for r in train.groupBy("label").count().collect()}
    total, k = sum(counts.values()), len(counts)
    weights = {lab: total / (k * n) for lab, n in counts.items()}
    mapping = F.create_map(*[x for lab, w in weights.items()
                             for x in (F.lit(lab), F.lit(w))])
    train = train.withColumn("weight", mapping[F.col("label")])

    pipeline = Pipeline(stages=[
        Tokenizer(inputCol="review_text", outputCol="tokens"),
        StopWordsRemover(inputCol="tokens", outputCol="clean"),
        CountVectorizer(inputCol="clean", outputCol="tf", vocabSize=20000, minDF=3),
        IDF(inputCol="tf", outputCol="features"),
        LogisticRegression(featuresCol="features", labelCol="label",
                           weightCol="weight", maxIter=30, regParam=0.02),
    ])
    model = pipeline.fit(train)
    return model, model.transform(test)


def score(pred, metric):
    return MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName=metric).evaluate(pred)


# ---- Model A: 3 classes (positive / neutral / negative) ----
label3 = (F.when(F.col("sentiment") == "negative", 0.0)
           .when(F.col("sentiment") == "neutral", 1.0)
           .otherwise(2.0))
model3, pred3 = train_and_test(silver, label3)

# ---- Model B: 2 classes (positive vs negative, neutral left out) ----
label2 = (F.when(F.col("sentiment") == "negative", 0.0)
           .when(F.col("sentiment") == "positive", 1.0))
model2, pred2 = train_and_test(silver, label2)

metrics = pd.DataFrame([
    {"model": "3-class", "metric": "accuracy", "value": round(score(pred3, "accuracy"), 4)},
    {"model": "3-class", "metric": "f1_weighted", "value": round(score(pred3, "f1"), 4)},
    {"model": "2-class", "metric": "accuracy", "value": round(score(pred2, "accuracy"), 4)},
    {"model": "2-class", "metric": "f1_weighted", "value": round(score(pred2, "f1"), 4)},
])
metrics.to_csv("data/gold/model_metrics.csv", index=False)
print(metrics.to_string(index=False))

# ---- confusion matrix and per-class report for the 3-class model ----
cm = (pred3.groupBy("label", "prediction").count().toPandas()
      .rename(columns={"count": "reviews"}))
cm["actual"] = cm["label"].astype(int).map(dict(enumerate(CLASSES)))
cm["predicted"] = cm["prediction"].astype(int).map(dict(enumerate(CLASSES)))
cm = cm[["actual", "predicted", "reviews"]].sort_values(["actual", "predicted"])
cm.to_csv("data/gold/confusion_matrix.csv", index=False)

rows = []
for c in CLASSES:
    tp = cm[(cm.actual == c) & (cm.predicted == c)].reviews.sum()
    actual_n = cm[cm.actual == c].reviews.sum()
    pred_n = cm[cm.predicted == c].reviews.sum()
    precision = tp / pred_n if pred_n else 0
    recall = tp / actual_n if actual_n else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    rows.append({"class": c, "precision": round(precision, 3), "recall": round(recall, 3),
                 "f1": round(f1, 3), "reviews": int(actual_n)})
report = pd.DataFrame(rows)
report.to_csv("data/gold/model_class_report.csv", index=False)
print("\nPer-class report (3-class model)")
print(report.to_string(index=False))

# ---- export the 3-class model weights so the dashboard can score a typed review
#      without needing Spark ----
cv, idf, lr = model3.stages[2], model3.stages[3], model3.stages[4]
coef = lr.coefficientMatrix.toArray()
weights_df = pd.DataFrame({
    "word": cv.vocabulary,
    "idf": idf.idf.toArray(),
    "w_negative": coef[0], "w_neutral": coef[1], "w_positive": coef[2],
})
weights_df.to_csv("data/gold/model_weights.csv", index=False, float_format="%.6g")
with open("data/gold/model_intercepts.json", "w") as f:
    json.dump(dict(zip(CLASSES, [float(x) for x in lr.interceptVector.toArray()])), f)

# ---- self-check: pure-Python scoring must agree with Spark's predictions ----
vocab = weights_df.set_index("word")
intercepts = json.load(open("data/gold/model_intercepts.json"))


def python_predict(text):
    counts = {}
    for tok in re.findall(r"[a-z]+", text.lower()):
        if tok in vocab.index:
            counts[tok] = counts.get(tok, 0) + 1
    scores = {}
    for c in CLASSES:
        s = intercepts[c]
        for tok, n in counts.items():
            s += n * vocab.at[tok, "idf"] * vocab.at[tok, f"w_{c}"]
        scores[c] = s
    return max(scores, key=scores.get)


sample = pred3.select("review_text", "prediction").limit(500).collect()
agree = sum(python_predict(r["review_text"]) == CLASSES[int(r["prediction"])] for r in sample)
print(f"\nSelf-check: pure-Python scoring matches Spark on {agree}/{len(sample)} reviews")

print("\nModel files saved in data/gold/")
spark.stop()
