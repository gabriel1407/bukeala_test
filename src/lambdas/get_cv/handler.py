"""Handler Lambda para consulta de CV por id.

Mantiene responsabilidades mínimas:
- Parsear request
- Delegar a caso de uso
- Formatear respuesta HTTP
"""

import json
from pathlib import Path
import sys

import boto3

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from common.adapters import DynamoCvRepositoryAdapter, JsonSerializer
from common.config import get_aws_runtime_config
from common.observability import MetricUnit, build_observability
from common.use_cases import GetCvUseCase


logger, metrics = build_observability("get-cv")

JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
}


def _build_use_case() -> tuple[GetCvUseCase, str]:
    """Construye dependencias concretas para el caso de uso de consulta."""

    config = get_aws_runtime_config()
    dynamodb = boto3.resource("dynamodb", region_name=config.region, endpoint_url=config.endpoint_url)
    table = dynamodb.Table(config.dynamodb_table_name)
    repository = DynamoCvRepositoryAdapter(table)
    return GetCvUseCase(repository=repository), config.dynamodb_table_name


def _json_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload, default=JsonSerializer.default, ensure_ascii=False, indent=2),
    }


def _ordered_cv_payload(item: dict) -> dict:
    ordered_fields = [
        "cv_id",
        "file_name",
        "file_size",
        "uploaded_at",
        "created_at",
        "bucket",
        "object_key",
        "etag",
        "summary_300",
    ]

    payload = {field: item[field] for field in ordered_fields if field in item}
    for key, value in item.items():
        if key not in payload:
            payload[key] = value
    return payload


@metrics.log_metrics
@logger.inject_lambda_context(log_event=True)
def handler(event, context):
    """Punto de entrada Lambda para API Gateway (GET /cv/{id})."""

    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}
    cv_id_raw = path_params.get("id") or query_params.get("id")
    cv_id = cv_id_raw.strip("/") if isinstance(cv_id_raw, str) else cv_id_raw

    if not cv_id:
        metrics.add_metric(name="MissingCvId", unit=MetricUnit.Count, value=1)
        logger.warning("Missing cv id in request")
        return _json_response(400, {"message": "cv id is required"})

    if isinstance(cv_id, str) and "/" in cv_id:
        metrics.add_metric(name="InvalidCvId", unit=MetricUnit.Count, value=1)
        logger.warning("Invalid cv id format", extra={"cv_id": cv_id})
        return _json_response(400, {"message": "invalid cv id format"})

    use_case, table_name = _build_use_case()
    item = use_case.execute(cv_id)

    if not item:
        metrics.add_metric(name="CvNotFound", unit=MetricUnit.Count, value=1)
        logger.info("CV not found", extra={"cv_id": cv_id})
        return _json_response(404, {"message": "CV not found"})

    metrics.add_metric(name="CvFound", unit=MetricUnit.Count, value=1)
    logger.info("CV found", extra={"cv_id": cv_id})

    return _json_response(
        200,
        {
            "message": "CV retrieved successfully",
            "data": _ordered_cv_payload(item),
        },
    )
