# Report and presentation checklist

Take a screenshot at each step. Numbers below are from the tested run.

| Step | Screenshot / number to capture | Report chapter |
|---|---|---|
| 01_bronze.py | "Bronze rows: 189,874" and the 5-column schema | Implementation |
| 02_silver.py | Before/after table (189,874 to 164,982) and `data/silver_quality_report.csv` | Implementation, Data quality |
| 03_gold.py | The list of saved Gold files | Implementation |
| 04_model.py | Accuracy, F1, confusion matrix, per-class report | Results |
| Dashboard | One screenshot per tab (Overview, Categories, Price, Words, Model) | Results and dashboard |
| Spark UI | Optional: screenshot of the Spark UI at localhost:4040 while a script runs | Architecture |

## Data quality findings (for the slide)
- 24,862 exact duplicate rows (13%)
- 5 rows with a broken rating (a product name in the rating column)
- 25 rows with empty review text
- Price text had broken symbol encoding
- "Nan" review titles

## Limitations to state
- Single platform (Flipkart), short reviews, no dates, no customer IDs
- 5-star reviews are the majority, so classes are imbalanced
- Only about half of the review texts are unique, so accuracy may be slightly optimistic
- Categories come from keyword rules on product names
- The review title is not used as a model input because it is tied to the rating
