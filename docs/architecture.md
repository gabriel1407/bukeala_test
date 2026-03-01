# Arquitectura de la solución

## Flujo principal
1. Cliente llama `POST /cv/upload-url` para obtener URL prefirmada de S3.
2. Cliente sube el archivo `.txt` con `PUT` al URL prefirmado.
3. Evento `ObjectCreated:*` dispara la Lambda `process_cv`.
4. `process_cv` lee el contenido, extrae `summary_300` y metadatos del objeto.
5. Lambda persiste el registro en DynamoDB (`cv_records`) con `cv_id` como PK.

## Bonus API
1. API Gateway expone `GET /cv/{id}`.
2. Lambda `get_cv` consulta en DynamoDB por `cv_id`.
3. Responde `200` con el registro o `404` cuando no existe.

## Observabilidad
- Logs estructurados y métricas con módulo interno en `src/lambdas/common/observability.py`.

## Diagrama

```mermaid
flowchart LR
    U[Usuario/Cliente] -->|POST /cv/upload-url| APIGW[API Gateway HTTP]
    APIGW --> L3[Lambda\nupload_cv_url]
    L3 -->|Presigned URL| U

    U -->|PUT CV .txt| S3[(S3 Bucket\ncv-uploads)]
    S3 -->|ObjectCreated| L1[Lambda\nprocess_cv]
    L1 -->|PutItem| DDB[(DynamoDB\ncv_records)]

    C[Cliente API] -->|GET /cv/{id}| APIGW
    APIGW --> L2[Lambda\nget_cv]
    L2 -->|GetItem| DDB
```
