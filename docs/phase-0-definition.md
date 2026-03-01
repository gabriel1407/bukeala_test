# Fase 0 - Definición funcional y técnica

## Objetivo
Implementar un flujo serverless que procese CVs en `.txt` cargados en S3, extraiga un resumen de 300 caracteres, recupere metadatos del archivo y almacene todo en DynamoDB.

## Alcance MVP
- Ingesta de archivos `.txt` en bucket S3.
- Disparo automático de Lambda por evento `ObjectCreated`.
- Procesamiento de contenido y extracción de `summary_300 = text[:300]`.
- Persistencia de registro en DynamoDB.

## Alcance Bonus
- API Gateway + Lambda para consultar CV por `cv_id`.

## Contrato técnico (propuesto)
### S3
- Bucket: `cv-uploads` (nombre final definido por IaC)
- Key sugerida: `cv/<cv_id>.txt`

### DynamoDB
- Tabla: `cv_records`
- PK: `cv_id` (String)
- Atributos:
  - `file_name` (String)
  - `file_size` (Number)
  - `uploaded_at` (String - ISO8601)
  - `summary_300` (String)
  - `bucket` (String)
  - `object_key` (String)
  - `etag` (String)
  - `created_at` (String - ISO8601)

### Lambda process_cv
Entrada: evento S3 `ObjectCreated`.

Salida lógica: `PutItem` en DynamoDB.

Reglas:
- Procesar solo archivos con extensión `.txt`.
- Decodificar bytes con `utf-8` y `errors="replace"`.
- Resumen de máximo 300 caracteres.
- Si falla procesamiento, log estructurado y error explícito.

### API Bonus get_cv
- Endpoint: `GET /cv/{id}`
- 200: retorna registro completo.
- 404: `{"message": "CV not found"}`

## Supuestos
- Se usará una cuenta AWS real para despliegue y pruebas.
- Terraform definirá toda la infraestructura del entorno.
- No se requiere NLP, solo truncamiento de texto.

## Riesgos y mitigación
- **Duplicidad de eventos S3**: usar `cv_id` estable e idempotencia por clave primaria.
- **Codificación inválida**: `errors="replace"`.
- **Archivos no válidos**: validar extensión y registrar rechazo.

## Definition of Done (MVP)
- Flujo end-to-end operativo en AWS:
  1. Upload `.txt` a S3.
  2. Trigger Lambda.
  3. Registro persistido en DynamoDB.
- README con pasos reproducibles.
- Logs claros para diagnóstico.

## Definition of Done (Bonus)
- Endpoint `GET /cv/{id}` funcionando en AWS.
- Manejo de `404` y errores controlados.
