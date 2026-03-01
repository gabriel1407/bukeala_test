"""Puertos (interfaces) para aplicar inversión de dependencias (DIP)."""

from typing import Any, Protocol

from .domain import CvRecord, ObjectMetadata


class ObjectStoragePort(Protocol):
    """Abstracción para leer contenido y metadatos desde almacenamiento de objetos."""

    def read_text(self, bucket: str, object_key: str) -> str:
        ...

    def read_metadata(self, bucket: str, object_key: str) -> ObjectMetadata:
        ...


class CvRepositoryPort(Protocol):
    """Abstracción para persistencia/consulta de CVs."""

    def save(self, record: CvRecord) -> None:
        ...

    def get_by_id(self, cv_id: str) -> dict[str, Any] | None:
        ...
