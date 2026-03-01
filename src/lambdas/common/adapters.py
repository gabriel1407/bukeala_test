"""Implementaciones concretas de puertos usando boto3."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from .domain import CvRecord, ObjectMetadata


class S3ObjectStorageAdapter:
    """Adaptador de almacenamiento de objetos sobre S3."""

    def __init__(self, s3_client):
        self._s3_client = s3_client

    def read_text(self, bucket: str, object_key: str) -> str:
        response = self._s3_client.get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read().decode("utf-8", errors="replace")

    def read_metadata(self, bucket: str, object_key: str) -> ObjectMetadata:
        response = self._s3_client.head_object(Bucket=bucket, Key=object_key)
        return ObjectMetadata(
            size=int(response["ContentLength"]),
            etag=response.get("ETag", ""),
            last_modified=response["LastModified"],
        )


class DynamoCvRepositoryAdapter:
    """Repositorio de CVs sobre DynamoDB."""

    def __init__(self, dynamo_table):
        self._table = dynamo_table

    def save(self, record: CvRecord) -> None:
        self._table.put_item(Item=record.__dict__)

    def get_by_id(self, cv_id: str) -> dict[str, Any] | None:
        response = self._table.get_item(Key={"cv_id": cv_id})
        return response.get("Item")


class JsonSerializer:
    """Serializador para tipos no JSON nativos devueltos por DynamoDB."""

    @staticmethod
    def default(value: Any):
        if isinstance(value, Decimal):
            if value % 1 == 0:
                return int(value)
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"Type not serializable: {type(value)}")
