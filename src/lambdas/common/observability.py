"""Observabilidad liviana sin dependencias externas para AWS Lambda."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable


class MetricUnit:
    """Unidades de métricas compatibles con la interfaz usada en handlers."""

    Count = "Count"


@dataclass
class _SimpleLogger:
    service_name: str
    _context: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self._logger = logging.getLogger(self.service_name)
        if not self._logger.handlers:
            logging.basicConfig(level=logging.INFO)

    def append_keys(self, **kwargs):
        for key, value in kwargs.items():
            if value is not None:
                self._context[key] = str(value)

    def inject_lambda_context(self, log_event: bool = False):
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(event, context):
                if context is not None:
                    self.append_keys(
                        function_name=getattr(context, "function_name", None),
                        request_id=getattr(context, "aws_request_id", None),
                    )
                if log_event:
                    self.info("lambda_event", extra={"event": event})
                return func(event, context)

            return wrapper

        return decorator

    def info(self, message: str, extra: dict | None = None):
        payload = {"service": self.service_name, **self._context, "message": message}
        if extra:
            payload.update(extra)
        self._logger.info(json.dumps(payload, default=str))

    def warning(self, message: str, extra: dict | None = None):
        payload = {"service": self.service_name, **self._context, "message": message}
        if extra:
            payload.update(extra)
        self._logger.warning(json.dumps(payload, default=str))


@dataclass
class _SimpleMetrics:
    namespace: str
    service_name: str
    _metrics: list[dict] = field(default_factory=list)

    def add_metric(self, name: str, unit: str, value: float | int):
        self._metrics.append(
            {
                "namespace": self.namespace,
                "service": self.service_name,
                "name": name,
                "unit": unit,
                "value": value,
            }
        )

    def log_metrics(self, func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper


def build_observability(service_name: str):
    """Construye logger y métricas con interfaz estable para los handlers."""

    logger = _SimpleLogger(service_name=service_name)
    metrics = _SimpleMetrics(namespace="Bukeala", service_name=service_name)
    return logger, metrics


__all__ = ["build_observability", "MetricUnit"]
