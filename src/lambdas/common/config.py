"""Configuración de runtime para Lambdas.

Centraliza lectura de variables de entorno para evitar duplicación en handlers.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AwsRuntimeConfig:
    """Valores necesarios para construir clientes AWS en runtime."""

    region: str
    endpoint_url: str | None
    dynamodb_table_name: str


def get_aws_runtime_config() -> AwsRuntimeConfig:
    """Resuelve región, endpoint y tabla DynamoDB desde variables de entorno."""

    endpoint = os.getenv("AWS_ENDPOINT_URL")

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    table_name = os.environ["DYNAMODB_TABLE_NAME"]

    return AwsRuntimeConfig(
        region=region,
        endpoint_url=endpoint,
        dynamodb_table_name=table_name,
    )
