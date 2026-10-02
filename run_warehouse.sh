#!/usr/bin/env bash
# Loads the star schema into PostgreSQL and runs the SQL analysis.
# Start PostgreSQL first (see README), then:  bash run_warehouse.sh
set -e
python scripts/05_warehouse.py
python scripts/06_sql_report.py
