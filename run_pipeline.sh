#!/usr/bin/env bash
# Core pipeline (no database needed). Use from the repo root:  bash run_pipeline.sh
set -e
python scripts/01_bronze.py
python scripts/02_silver.py
python scripts/03_gold.py
python scripts/04_model.py
echo "Pipeline finished. Next: bash run_warehouse.sh  (needs PostgreSQL)  or  streamlit run dashboard/app.py"
