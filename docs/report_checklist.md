# Report and presentation checklist

Take a screenshot at each step.

| Step | Screenshot / number to capture | Report chapter |
|---|---|---|
| Architecture | `docs/architecture.png` | Architecture |
| 01_bronze.py | "Bronze rows: 189,874" and the 5-column schema | Implementation |
| 02_silver.py | Before/after table and `data/silver_quality_report.csv` | Implementation, Data quality |
| 03_gold.py | The list of saved Gold files | Implementation |
| 04_model.py | Accuracy, F1, confusion matrix, per-class report | Results |
| 05_warehouse.py | "loaded ..." lines and the "Check ... OK" line | Warehouse |
| sql/schema.sql | Star schema (draw the 5 tables and their keys) | Warehouse |
| 06_sql_report.py | A few of the 10 query results (`docs/sql_results.txt`) | Results |
| 08_hive_tables.py | The table list, the 9 category partitions and the query results | Hive tables |
| 07_benchmark.py | The timing table (`data/gold/benchmark.csv`) | Performance |
| Dashboard | One screenshot per tab (Overview, Categories, Price, Words, Model) | Results and dashboard |

## Data quality findings (for the slide)
- 24,862 exact duplicate rows (13%)
- 5 rows with a broken rating (a product name in the rating column)
- 25 rows with empty review text
- Price text had broken symbol encoding
- "Nan" review titles

## Honest notes for the benchmark slide
- The data fits in memory, so Pandas can be as fast as or faster than Spark here.
  Spark's advantage appears with much bigger data or a cluster. Report your own
  timings and say this plainly.

## Limitations to state
- Single platform (Flipkart), short reviews, no dates, no customer IDs
- 5-star reviews are the majority, so classes are imbalanced
- Only about half of the review texts are unique, so accuracy may be slightly optimistic
- Categories come from keyword rules on product names
- The review title is not used as a model input because it is tied to the rating
- Spark ran in local mode on one machine (no Hadoop cluster)
