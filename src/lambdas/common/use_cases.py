"""Casos de uso de la aplicación (lógica de orquestación de negocio)."""

from datetime import datetime, timezone

from .domain import CvRecord, InvalidFileExtensionError, ProcessCvCommand
from .ports import CvRepositoryPort, ObjectStoragePort


class ProcessCvUseCase:
    """Orquesta el procesamiento de un CV y su persistencia."""

    def __init__(self, storage: ObjectStoragePort, repository: CvRepositoryPort):
        self._storage = storage
        self._repository = repository

    def execute(self, command: ProcessCvCommand) -> CvRecord:
        """Ejecuta el flujo completo de procesamiento para un archivo de CV."""

        if not command.object_key.lower().endswith(".txt"):
            raise InvalidFileExtensionError("Only .txt files are supported")

        text = self._storage.read_text(command.bucket, command.object_key)
        metadata = self._storage.read_metadata(command.bucket, command.object_key)
        record = CvRecord.from_content(command=command, text=text, metadata=metadata, now=datetime.now(timezone.utc))
        self._repository.save(record)
        return record


class GetCvUseCase:
    """Obtiene un CV persistido por su identificador."""

    def __init__(self, repository: CvRepositoryPort):
        self._repository = repository

    def execute(self, cv_id: str):
        """Retorna el registro del CV o None si no existe."""

        return self._repository.get_by_id(cv_id)
