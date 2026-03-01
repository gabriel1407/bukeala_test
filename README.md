# bukeala_test

Sistema serverless en AWS para procesar CVs `.txt` con S3 + Lambda + DynamoDB y consulta por API Gateway.

## Arquitectura

- API `POST /cv/upload` recibe archivo `.txt` en `multipart/form-data`.
- Evento `ObjectCreated:*` dispara Lambda `process_cv`.
- `process_cv` extrae `summary_300`, metadatos y guarda en DynamoDB.
- API Gateway HTTP + Lambda `get_cv` para `GET /cv/{id}`.

Ver diagrama en `docs/architecture.md`.

## Requisitos

- Terraform >= 1.6
- AWS CLI autenticado (`AWS_PROFILE` o variables de entorno)
- Permisos IAM para S3, Lambda, IAM, DynamoDB, API Gateway y CloudWatch Logs

## Configuración

Archivo: `infra/terraform/aws-account.tfvars`

Ejemplo:

```hcl
aws_region          = "us-east-1"
project_name        = "bukeala"
bucket_name         = "bukeala-buckets-test"
create_bucket       = false
dynamodb_table_name = "cv_records"
```

## Despliegue en AWS real

```bash
cd infra/terraform
terraform init
terraform workspace new aws-real || terraform workspace select aws-real
terraform apply -var-file=aws-account.tfvars -auto-approve
terraform output
```

Output clave:

- `api_base_url`

## Makefile

```bash
make terraform-init
make terraform-plan
make terraform-apply
make terraform-output
make test
```

Opcional (perfil distinto):

```bash
make terraform-apply AWS_PROFILE=gabriel1407
```

## Demo visual con 2 APIs

### API 1: Upload de archivo (form-data)

```bash
API_BASE_URL=$(terraform -chdir=infra/terraform output -raw api_base_url)

curl -sS -X POST "$API_BASE_URL/cv/upload" \
  -F "cv_id=gabriel_cv" \
  -F "file=@docs/gabriel_cv.txt;type=text/plain"
```

Respuesta esperada (resumen):

```json
{
  "message": "CV uploaded successfully",
  "data": {
    "cv_id": "gabriel_cv",
    "file_name": "gabriel_cv.txt",
    "bucket": "bukeala-buckets-test",
    "object_key": "cv/gabriel_cv.txt"
  },
  "links": {
    "api_base_url": "https://.../",
    "get_path": "/cv/gabriel_cv",
    "get_url": "https://.../cv/gabriel_cv",
    "get_url_with_trailing_slash": "https://.../cv/gabriel_cv/"
  },
  "meta": {
    "status": "accepted"
  }
}
```

### API 2: Consultar CV procesado

```bash
curl -i "$API_BASE_URL/cv/gabriel_cv"
```

Respuesta esperada (resumen):

```json
{
  "message": "CV retrieved successfully",
  "data": {
    "cv_id": "gabriel_cv",
    "file_name": "gabriel_cv.txt",
    "file_size": 3892,
    "uploaded_at": "2026-03-01T04:19:42.483Z",
    "created_at": "2026-03-01T04:19:47.134741+00:00",
    "bucket": "bukeala-buckets-test",
    "object_key": "cv/gabriel_cv.txt",
    "etag": "...",
    "summary_300": "..."
  }
}
```

Si al primer intento devuelve `404`, espera unos segundos y reintenta (trigger asíncrono).

## Verificación en DynamoDB

```bash
aws dynamodb get-item \
  --table-name cv_records \
  --key '{"cv_id":{"S":"gabriel_cv"}}' \
  --region us-east-1
```
