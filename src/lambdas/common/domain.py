"""Entidades de dominio y reglas de negocio del procesamiento de CV."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


class InvalidFileExtensionError(ValueError):
    """Se lanza cuando el archivo recibido no es .txt."""

    pass


@dataclass(frozen=True)
class ObjectMetadata:
    """Metadatos mínimos de un objeto en almacenamiento."""

    size: int
    etag: str
    last_modified: datetime


@dataclass(frozen=True)
class ProcessCvCommand:
    """Comando de entrada para el caso de uso de procesamiento."""

    bucket: str
    object_key: str
    event_time: str | None


@dataclass(frozen=True)
class CvRecord:
    """Modelo persistente del CV ya procesado."""

    cv_id: str
    file_name: str
    file_size: int
    uploaded_at: str
    summary_300: str
    bucket: str
    object_key: str
    etag: str
    created_at: str

    @staticmethod
    def from_content(
        command: ProcessCvCommand,
        text: str,
        metadata: ObjectMetadata,
        now: datetime,
    ) -> "CvRecord":
        """Construye un registro de CV aplicando reglas de negocio.

        - Valida extensión .txt
        - Calcula cv_id a partir del nombre de archivo
        - Genera resumen de 300 caracteres
        """

        if not command.object_key.lower().endswith(".txt"):
            raise InvalidFileExtensionError("Only .txt files are supported")

        file_name = command.object_key.rsplit("/", 1)[-1]
        cv_id = file_name[:-4] if file_name.lower().endswith(".txt") and file_name[:-4] else str(uuid4())
        uploaded_at = command.event_time or _isoformat_utc(metadata.last_modified)

        return CvRecord(
            cv_id=cv_id,
            file_name=file_name,
            file_size=int(metadata.size),
            uploaded_at=uploaded_at,
            summary_300=text[:300],
            bucket=command.bucket,
            object_key=command.object_key,
            etag=metadata.etag.replace('"', ""),
            created_at=_isoformat_utc(now),
        )


def _isoformat_utc(value: datetime) -> str:
    """Normaliza fechas al formato ISO 8601 en UTC."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
