from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_ROOT = "/opt/airflow/project"


default_args = {
    "owner": "koltrust",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="koltrust_batch_pipeline",
    default_args=default_args,
    description="Build, sync, and validate KOLTrust datasets.",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["koltrust", "bigdata", "etl"],
) as dag:
    build_dataset = BashOperator(
        task_id="build_dataset",
        bash_command=f"cd {PROJECT_ROOT} && python -m build-dataset",
    )

    validate_data = BashOperator(
        task_id="validate_data",
        bash_command=f"cd {PROJECT_ROOT} && python -m validate-data",
    )

    build_dataset >> validate_data
