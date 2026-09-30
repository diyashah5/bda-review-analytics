# Flipkart Product Review Analytics (BDA Mini Project)

Big Data Analytics mini project: analysing Flipkart product reviews with **PySpark**
and predicting review sentiment with **Spark MLlib**.

## Pipeline

```
flipkart_product.csv  ->  Bronze (raw Parquet)  ->  Silver (cleaned)  ->  Gold (CSV tables)  ->  Dashboard
                                                          |
                                                          +->  MLlib sentiment model
```

| Layer | Script | What it does |
|---|---|---|
| Bronze | `scripts/01_bronze.py` | Reads the raw CSV and saves it as Parquet without changes |
| Silver | `scripts/02_silver.py` | Removes duplicates and broken rows, cleans price and review text, adds sentiment, category and price band |
| Gold | `scripts/03_gold.py` | Builds small analysis tables with Spark SQL (`data/gold/*.csv`) |
| Model | `scripts/04_model.py` | TF-IDF + Logistic Regression on review text, saves metrics and model weights |
| Dashboard | `dashboard/app.py` | Streamlit dashboard that reads only the Gold CSV files |

## Results (tested run)

- 189,874 raw rows, 164,982 rows after cleaning
- Sentiment (from star rating): about 76% positive, 8% neutral, 15% negative
- 3-class model (positive / neutral / negative): about 75% accuracy, F1 0.79
- Positive vs negative only: about 92% accuracy, F1 0.92
- Neutral reviews are the hardest class to predict

## How to run

Put `flipkart_product.csv` in the `data/` folder, then from the repo root:

```bash
pip install -r requirements.txt      # Java is also needed for PySpark
bash run_pipeline.sh                 # runs all four scripts
streamlit run dashboard/app.py
```

Or run the scripts one by one:

```bash
python scripts/01_bronze.py
python scripts/02_silver.py
python scripts/03_gold.py
python scripts/04_model.py
```

## For the dashboard teammate

Spark is **not** needed. The Gold tables are already in `data/gold/`:

```bash
pip install streamlit plotly pandas numpy
streamlit run dashboard/app.py
```

The dashboard is `dashboard/app.py`. It reads `data/gold/cube.csv`, `products.csv`,
`top_words.csv`, `word_signals.csv` and the `model_*.csv` files. Feel free to change the
layout, colors and charts. If the pipeline is re-run, the Gold files are regenerated
with the same column names.

## Notes and limitations

- Data: Flipkart product reviews from Kaggle. Single platform, short reviews, no dates.
- The review title is not used as a model input because it is tied to the star rating.
- Categories are derived from product names with keyword rules.
- Only about half of the review texts are unique, so accuracy may be slightly optimistic.
- See `docs/report_checklist.md` for what to screenshot for the report.
