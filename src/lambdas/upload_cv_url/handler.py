"""Handler Lambda para recibir upload de CV por multipart/form-data.

Expone un endpoint API para simplificar demos:
- POST /cv/upload
"""

import base64
import json
import os
import re
import sys
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from uuid import uuid4

import boto3

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from common.observability import MetricUnit, build_observability


logger, metrics = build_observability("upload-cv-url")

JSON_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
}


def _json_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": JSON_HEADERS,
        "body": json.dumps(payload, ensure_ascii=False, indent=2),
    }


def _safe_cv_id(raw_value: str | None) -> str:
    if not raw_value:
        return str(uuid4())
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_value.strip())
    return cleaned or str(uuid4())


def _get_header(headers: dict | None, name: str) -> str | None:
    if not headers:
        return None
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def _parse_multipart(event: dict) -> tuple[dict[str, str], str, bytes]:
    headers = event.get("headers") or {}
    content_type = _get_header(headers, "content-type")
    if not content_type or "multipart/form-data" not in content_type.lower():
        raise ValueError("Content-Type must be multipart/form-data")

    body_raw = event.get("body")
    if body_raw is None:
        raise ValueError("body is required")

    body_bytes = base64.b64decode(body_raw) if event.get("isBase64Encoded") else body_raw.encode("utf-8")
    raw_message = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body_bytes
    )
    message = BytesParser(policy=default).parsebytes(raw_message)

    fields: dict[str, str] = {}
    file_name = ""
    file_content = b""

    for part in message.iter_parts():
        name = part.get_param("name", header="Content-Disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            file_name = filename
            file_content = payload
        elif name:
            fields[name] = payload.decode("utf-8", errors="replace")

    if not file_name or not file_content:
        raise ValueError("file is required in form-data")

    return fields, file_name, file_content


def _build_base_url(event: dict) -> str:
    request_context = event.get("requestContext") or {}
    domain_name = request_context.get("domainName")
    stage = request_context.get("stage")
    if not domain_name:
        return ""

    base = f"https://{domain_name}"
    if stage and stage != "$default":
        base = f"{base}/{stage}"
    return f"{base.rstrip('/')}/"


@metrics.log_metrics
@logger.inject_lambda_context(log_event=True)
def handler(event, context):
    raw_path = event.get("rawPath")
    if isinstance(raw_path, str) and raw_path.rstrip("/") != "/cv/upload":
        return _json_response(404, {"message": "Not Found"})

    bucket_name = os.environ["CV_UPLOAD_BUCKET"]
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    s3_client = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)

    try:
        fields, file_name, file_content = _parse_multipart(event)
    except ValueError as exc:
        metrics.add_metric(name="InvalidUploadPayload", unit=MetricUnit.Count, value=1)
        return _json_response(400, {"message": str(exc)})

    cv_id = _safe_cv_id(fields.get("cv_id") or file_name.rsplit(".", 1)[0])

    if file_name and not file_name.lower().endswith(".txt"):
        metrics.add_metric(name="InvalidUploadExtension", unit=MetricUnit.Count, value=1)
        return _json_response(400, {"message": "Only .txt files are supported"})

    object_key = f"cv/{cv_id}.txt"
    base_url = _build_base_url(event)
    get_path = f"/cv/{cv_id}"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=file_content,
        ContentType="text/plain",
    )

    metrics.add_metric(name="UploadReceived", unit=MetricUnit.Count, value=1)
    logger.info("CV uploaded through API", extra={"cv_id": cv_id, "bucket": bucket_name, "object_key": object_key})

    get_url = f"{base_url.rstrip('/')}{get_path}" if base_url else get_path
    get_url_with_trailing_slash = f"{base_url}cv/{cv_id}/" if base_url else f"{get_path}/"

    return _json_response(
        202,
        {
            "message": "CV uploaded successfully",
            "data": {
                "cv_id": cv_id,
                "file_name": file_name,
                "bucket": bucket_name,
                "object_key": object_key,
            },
            "links": {
                "api_base_url": base_url,
                "get_path": get_path,
                "get_url": get_url,
                "get_url_with_trailing_slash": get_url_with_trailing_slash,
            },
            "meta": {
                "status": "accepted",
            },
        },
    )
