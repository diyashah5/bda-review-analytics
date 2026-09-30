"""Flipkart Product Review Analytics dashboard.
Run from the repo root:  streamlit run dashboard/app.py
It reads only the small CSV files in data/gold/, so Spark is NOT needed to run it.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

GOLD = Path(__file__).resolve().parent.parent / "data" / "gold"
COLORS = {"positive": "#2e9e6b", "neutral": "#e0a526", "negative": "#d64545"}
ORDER = ["negative", "neutral", "positive"]

st.set_page_config(page_title="Flipkart Review Analytics", page_icon="📊", layout="wide")


@st.cache_data
def load(name):
    return pd.read_csv(GOLD / f"{name}.csv")


needed = ["cube", "products", "top_words", "word_signals", "model_metrics",
          "confusion_matrix", "model_class_report", "model_weights"]
missing = [n for n in needed if not (GOLD / f"{n}.csv").exists()]
if missing:
    st.error(f"Missing files in data/gold/: {', '.join(missing)}. "
             "Run scripts 03_gold.py and 04_model.py first (or pull the latest repo).")
    st.stop()

cube, products = load("cube"), load("products")
top_words, signals = load("top_words"), load("word_signals")
metrics, cm = load("model_metrics"), load("confusion_matrix")
class_report, weights = load("model_class_report"), load("model_weights")

# ---------------- sidebar filters ----------------
st.sidebar.header("Filters")
all_cats = sorted(cube["category"].unique())
all_bands = sorted(cube["price_band"].unique())
cats = st.sidebar.multiselect("Category", all_cats, default=all_cats)
bands = st.sidebar.multiselect("Price band (Rs.)", all_bands, default=all_bands)
st.sidebar.caption("Filters apply to the Overview, Categories and Price tabs.")

f = cube[cube["category"].isin(cats) & cube["price_band"].isin(bands)]

st.title("📊 Flipkart Product Review Analytics")
st.caption("PySpark pipeline (Bronze → Silver → Gold) with a Spark MLlib sentiment model")

total = int(f["reviews"].sum())
if total == 0:
    st.warning("No reviews match these filters. Select at least one category and price band.")
    st.stop()

avg_rating = (f["rating"] * f["reviews"]).sum() / total
pct = f.groupby("sentiment")["reviews"].sum() / total * 100
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Reviews", f"{total:,}")
c2.metric("Average rating", f"{avg_rating:.2f} / 5")
c3.metric("Positive", f"{pct.get('positive', 0):.1f}%")
c4.metric("Negative", f"{pct.get('negative', 0):.1f}%")
c5.metric("Average price", f"Rs. {f['sum_price'].sum() / total:,.0f}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Overview", "Categories", "Price & products", "Words", "Model"])

# ---------------- tab 1: overview ----------------
with tab1:
    left, right = st.columns(2)
    dist = f.groupby("rating", as_index=False)["reviews"].sum()
    fig = px.bar(dist, x="rating", y="reviews", text_auto=".2s",
                 title="Rating distribution", color_discrete_sequence=["#3b6fd4"])
    fig.update_xaxes(type="category")
    left.plotly_chart(fig)

    sent = f.groupby("sentiment", as_index=False)["reviews"].sum()
    fig = px.pie(sent, names="sentiment", values="reviews", hole=0.5,
                 title="Sentiment split", color="sentiment", color_discrete_map=COLORS)
    right.plotly_chart(fig)

    st.info("Most reviews are 5-star, so the data is imbalanced. "
            "The model uses class weights to handle this.")

# ---------------- tab 2: categories ----------------
with tab2:
    left, right = st.columns(2)
    by_cat = f.groupby(["category", "sentiment"], as_index=False)["reviews"].sum()
    by_cat["share"] = by_cat["reviews"] / by_cat.groupby("category")["reviews"].transform("sum") * 100
    fig = px.bar(by_cat, y="category", x="share", color="sentiment", orientation="h",
                 title="Sentiment share by category (%)", color_discrete_map=COLORS,
                 category_orders={"sentiment": ORDER})
    left.plotly_chart(fig)

    avg = (f.assign(rw=f["rating"] * f["reviews"]).groupby("category")
           .agg(rw=("rw", "sum"), n=("reviews", "sum")).reset_index())
    avg["avg_rating"] = avg["rw"] / avg["n"]
    avg = avg.sort_values("avg_rating")
    fig = px.bar(avg, y="category", x="avg_rating", orientation="h", text_auto=".2f",
                 title="Average rating by category", color_discrete_sequence=["#3b6fd4"])
    fig.update_xaxes(range=[1, 5])
    right.plotly_chart(fig)

    vol = f.groupby("category", as_index=False)["reviews"].sum().sort_values("reviews")
    st.plotly_chart(px.bar(vol, y="category", x="reviews", orientation="h",
                           title="Number of reviews by category",
                           color_discrete_sequence=["#7a8ca8"]))

# ---------------- tab 3: price and products ----------------
with tab3:
    left, right = st.columns(2)
    pb = f.groupby(["price_band", "sentiment"], as_index=False)["reviews"].sum()
    pb["share"] = pb["reviews"] / pb.groupby("price_band")["reviews"].transform("sum") * 100
    fig = px.bar(pb, x="price_band", y="share", color="sentiment",
                 title="Sentiment share by price band (%)", color_discrete_map=COLORS,
                 category_orders={"sentiment": ORDER})
    left.plotly_chart(fig)

    pr = (f.assign(rw=f["rating"] * f["reviews"]).groupby("price_band")
          .agg(rw=("rw", "sum"), n=("reviews", "sum")).reset_index())
    pr["avg_rating"] = pr["rw"] / pr["n"]
    fig = px.bar(pr, x="price_band", y="avg_rating", text_auto=".2f",
                 title="Average rating by price band", color_discrete_sequence=["#3b6fd4"])
    fig.update_yaxes(range=[1, 5])
    right.plotly_chart(fig)

    p = products[products["category"].isin(cats)]
    cols = ["product_name", "category", "reviews", "avg_rating", "pct_positive", "avg_price"]
    st.subheader("Most reviewed products")
    st.dataframe(p.sort_values("reviews", ascending=False).head(10)[cols], hide_index=True)
    st.subheader("Lowest rated products (100+ reviews)")
    st.dataframe(p.sort_values("avg_rating").head(10)[cols], hide_index=True)

# ---------------- tab 4: words ----------------
with tab4:
    st.caption("Stop words removed. Counts come from the Gold layer (Spark).")
    cols = st.columns(3)
    for col, s in zip(cols, ORDER):
        d = top_words[top_words["sentiment"] == s].sort_values("count").tail(15)
        fig = px.bar(d, x="count", y="word", orientation="h", title=f"Top words: {s}",
                     color_discrete_sequence=[COLORS[s]])
        col.plotly_chart(fig)

    left, right = st.columns(2)
    neg = signals.sort_values("neg_share", ascending=False).head(15).sort_values("neg_share")
    fig = px.bar(neg, x="neg_share", y="word", orientation="h",
                 title="Words most linked to negative reviews",
                 color_discrete_sequence=[COLORS["negative"]])
    left.plotly_chart(fig)
    pos = signals.sort_values("pos_share", ascending=False).head(15).sort_values("pos_share")
    fig = px.bar(pos, x="pos_share", y="word", orientation="h",
                 title="Words most linked to positive reviews",
                 color_discrete_sequence=[COLORS["positive"]])
    right.plotly_chart(fig)
    st.caption("Share = fraction of the word's uses that appear in that type of review "
               "(words used at least 300 times).")

# ---------------- tab 5: model ----------------
with tab5:
    m = metrics.set_index(["model", "metric"])["value"]
    a, b, c, d = st.columns(4)
    a.metric("3-class accuracy", f"{m[('3-class', 'accuracy')] * 100:.1f}%")
    b.metric("3-class F1", f"{m[('3-class', 'f1_weighted')]:.2f}")
    c.metric("Positive vs negative accuracy", f"{m[('2-class', 'accuracy')] * 100:.1f}%")
    d.metric("Positive vs negative F1", f"{m[('2-class', 'f1_weighted')]:.2f}")
    st.caption("TF-IDF + Logistic Regression (Spark MLlib), trained on review text only, "
               "80/20 split. Neutral reviews are the hardest to predict.")

    left, right = st.columns(2)
    grid = cm.pivot(index="actual", columns="predicted", values="reviews").reindex(
        index=ORDER, columns=ORDER)
    fig = px.imshow(grid, text_auto=True, color_continuous_scale="Blues",
                    title="Confusion matrix (actual vs predicted)")
    left.plotly_chart(fig)
    right.subheader("Per-class results")
    right.dataframe(class_report, hide_index=True)

    st.subheader("Try a review")
    text = st.text_area("Type a product review",
                        "Very good quality, totally worth the money")
    if st.button("Predict sentiment"):
        vocab = weights.set_index("word")
        intercepts = json.loads((GOLD / "model_intercepts.json").read_text())
        counts = {}
        for tok in re.findall(r"[a-z]+", text.lower()):
            if tok in vocab.index:
                counts[tok] = counts.get(tok, 0) + 1
        if not counts:
            st.warning("None of these words are known to the model. Try a longer review.")
        else:
            raw = np.array([
                intercepts[k] + sum(n * vocab.at[t, "idf"] * vocab.at[t, f"w_{k}"]
                                    for t, n in counts.items())
                for k in ORDER])
            prob = np.exp(raw - raw.max())
            prob = prob / prob.sum()
            out = pd.DataFrame({"sentiment": ORDER, "probability": prob})
            st.success(f"Predicted sentiment: {ORDER[int(prob.argmax())]}")
            st.plotly_chart(px.bar(out, x="sentiment", y="probability", color="sentiment",
                                   color_discrete_map=COLORS, range_y=[0, 1]))

st.divider()
st.caption("Data: Flipkart product reviews (Kaggle). Single platform, short reviews, "
           "no dates. Categories were derived from product names using keyword rules.")
