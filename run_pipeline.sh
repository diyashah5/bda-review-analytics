#!/usr/bin/env bash
# Runs the whole pipeline. Use from the repo root:  bash run_pipeline.sh
set -e
python scripts/01_bronze.py
python scripts/02_silver.py
python scripts/03_gold.py
python scripts/04_model.py
echo "Pipeline finished. Start the dashboard with: streamlit run dashboard/app.py"
