from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/project"

with DAG(
    dag_id="flipkart_review_analytics",
    description="Incrementally process review batches and refresh analytics",
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["pyspark", "reviews", "bda"],
) as dag:
    bronze = BashOperator(
        task_id="bronze_incremental_ingestion",
        bash_command=f"cd {PROJECT_DIR} && python scripts/01_bronze.py",
    )
    silver = BashOperator(
        task_id="silver_quality_and_transform",
        bash_command=f"cd {PROJECT_DIR} && python scripts/02_silver.py",
    )
    gold = BashOperator(
        task_id="gold_analytics",
        bash_command=f"cd {PROJECT_DIR} && python scripts/03_gold.py",
    )
    model = BashOperator(
        task_id="train_sentiment_models",
        bash_command=f"cd {PROJECT_DIR} && python scripts/04_model.py",
    )
    warehouse = BashOperator(
        task_id="load_postgres_warehouse",
        bash_command=f"cd {PROJECT_DIR} && python warehouse/load_gold.py",
    )

    bronze >> silver >> gold >> model >> warehouse