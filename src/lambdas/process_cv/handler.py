"""Handler Lambda para procesamiento de CV subido a S3.

Mantiene responsabilidades mínimas:
- Parsear evento
- Delegar a caso de uso
- Devolver respuesta HTTP
"""

import json
from pathlib import Path
import sys
from urllib.parse import unquote_plus

import boto3

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from common.adapters import DynamoCvRepositoryAdapter, S3ObjectStorageAdapter
from common.config import get_aws_runtime_config
from common.domain import InvalidFileExtensionError, ProcessCvCommand
from common.observability import MetricUnit, build_observability
from common.use_cases import ProcessCvUseCase


logger, metrics = build_observability("process-cv")


def _build_use_case() -> tuple[ProcessCvUseCase, str]:
    """Construye dependencias concretas para el caso de uso de procesamiento."""

    config = get_aws_runtime_config()
    s3_client = boto3.client("s3", region_name=config.region, endpoint_url=config.endpoint_url)
    dynamodb = boto3.resource("dynamodb", region_name=config.region, endpoint_url=config.endpoint_url)
    table = dynamodb.Table(config.dynamodb_table_name)

    storage = S3ObjectStorageAdapter(s3_client)
    repository = DynamoCvRepositoryAdapter(table)
    return ProcessCvUseCase(storage=storage, repository=repository), config.dynamodb_table_name


@metrics.log_metrics
@logger.inject_lambda_context(log_event=True)
def handler(event, context):
    """Punto de entrada Lambda para evento S3 ObjectCreated."""

    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    object_key = unquote_plus(record["s3"]["object"]["key"])

    logger.append_keys(bucket=bucket, object_key=object_key)
    logger.info("Received S3 event for CV processing")

    use_case, table_name = _build_use_case()
    logger.append_keys(table_name=table_name)

    try:
        cv_record = use_case.execute(
            ProcessCvCommand(
                bucket=bucket,
                object_key=object_key,
                event_time=record.get("eventTime"),
            )
        )
    except InvalidFileExtensionError:
        metrics.add_metric(name="InvalidFileExtension", unit=MetricUnit.Count, value=1)
        logger.warning("Unsupported file extension")
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Only .txt files are supported"}),
        }

    metrics.add_metric(name="ProcessedCv", unit=MetricUnit.Count, value=1)
    logger.info("CV processed and persisted", extra={"cv_id": cv_record.cv_id})

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "CV processed successfully",
                "cv_id": cv_record.cv_id,
                "table": table_name,
            }
        ),
    }
