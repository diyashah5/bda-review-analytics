"""HTTP API for review analytics and sentiment predictions."""
import csv
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


CLASSES = ("negative", "neutral", "positive")
TOKEN_PATTERN = re.compile(r"[a-z]+")
GOLD_DIR = Path(os.getenv("GOLD_DIR", "data/gold"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bda_user:bda_local_password@localhost:5432/review_warehouse",
)

app = FastAPI(title="Flipkart Review Analytics API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ReviewInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


def connect():
    return psycopg.connect(DATABASE_URL)


def where_filters(category, price_band):
    clauses = []
    values = []
    if category:
        clauses.append("c.category_name = %s")
        values.append(category)
    if price_band:
        clauses.append("pb.price_band_name = %s")
        values.append(price_band)
    return (" AND ".join(clauses) if clauses else "TRUE"), values


@lru_cache(maxsize=1)
def model_artifacts():
    with (GOLD_DIR / "model_intercepts.json").open(encoding="utf-8") as source:
        intercepts = json.load(source)
    weights = {}
    with (GOLD_DIR / "model_weights.csv").open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            weights[row["word"]] = (
                float(row["idf"]),
                float(row["w_negative"]),
                float(row["w_neutral"]),
                float(row["w_positive"]),
            )
    return intercepts, weights


def predict_sentiment(text):
    intercepts, weights = model_artifacts()
    token_counts = {}
    for token in TOKEN_PATTERN.findall(text.lower()):
        if token in weights:
            token_counts[token] = token_counts.get(token, 0) + 1
    if not token_counts:
        raise ValueError("No words in this review are known to the model.")

    scores = [intercepts[label] for label in CLASSES]
    for token, count in token_counts.items():
        idf, *coefficients = weights[token]
        for index, coefficient in enumerate(coefficients):
            scores[index] += count * idf * coefficient
    peak = max(scores)
    exponentials = [math.exp(score - peak) for score in scores]
    total = sum(exponentials)
    probabilities = {
        label: value / total for label, value in zip(CLASSES, exponentials)
    }
    prediction = max(probabilities, key=probabilities.get)
    return prediction, probabilities


@app.get("/health")
def health():
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except psycopg.Error as error:
        raise HTTPException(status_code=503, detail="Warehouse is unavailable") from error
    return {"status": "ok", "warehouse": "connected"}


@app.get("/analytics/summary")
def analytics_summary(category: str | None = None, price_band: str | None = None):
    filters, values = where_filters(category, price_band)
    with connect() as connection:
        aggregate = connection.execute(
            f"""SELECT COALESCE(SUM(f.review_count), 0),
                       COALESCE(SUM(f.rating * f.review_count), 0),
                       COALESCE(SUM(f.sum_price), 0)
                FROM fact_review_aggregate f
                JOIN dim_category c USING (category_id)
                JOIN dim_price_band pb USING (price_band_id)
                WHERE {filters}""",
            values,
        ).fetchone()
        sentiments = connection.execute(
            f"""SELECT s.sentiment_name, SUM(f.review_count)
                FROM fact_review_aggregate f
                JOIN dim_category c USING (category_id)
                JOIN dim_price_band pb USING (price_band_id)
                JOIN dim_sentiment s USING (sentiment_id)
                WHERE {filters}
                GROUP BY s.sentiment_name""",
            values,
        ).fetchall()

    total, rating_sum, price_sum = aggregate
    sentiment_counts = {name: count for name, count in sentiments}
    return {
        "reviews": total,
        "average_rating": rating_sum / total if total else 0,
        "average_price": float(price_sum / total) if total else 0,
        "sentiment_counts": sentiment_counts,
    }


@app.get("/analytics/filters")
def analytics_filters():
    with connect() as connection:
        categories = connection.execute(
            "SELECT category_name FROM dim_category ORDER BY category_name"
        ).fetchall()
        price_bands = connection.execute(
            "SELECT price_band_name FROM dim_price_band ORDER BY price_band_name"
        ).fetchall()
    return {
        "categories": [row[0] for row in categories],
        "price_bands": [row[0] for row in price_bands],
    }


@app.get("/analytics/products")
def analytics_products(
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    query = """SELECT p.product_name, c.category_name AS category, f.review_count AS reviews,
                      f.average_rating, f.positive_percent, f.negative_percent, f.average_price
               FROM fact_product_summary f
               JOIN dim_product p USING (product_id)
               JOIN dim_category c USING (category_id)"""
    values = []
    if category:
        query += " WHERE c.category_name = %s"
        values.append(category)
    query += " ORDER BY f.review_count DESC LIMIT %s"
    values.append(limit)
    with connect() as connection:
        rows = connection.execute(query, values).fetchall()
    columns = (
        "product_name", "category", "reviews", "average_rating",
        "positive_percent", "negative_percent", "average_price",
    )
    return [dict(zip(columns, row)) for row in rows]


@app.post("/predict/sentiment")
def sentiment_prediction(review: ReviewInput):
    try:
        prediction, probabilities = predict_sentiment(review.text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"sentiment": prediction, "probabilities": probabilities}