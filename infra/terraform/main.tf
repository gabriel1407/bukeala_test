locals {
  process_cv_function_name    = "${var.project_name}-process-cv"
  get_cv_function_name        = "${var.project_name}-get-cv"
  upload_cv_url_function_name = "${var.project_name}-upload-cv-url"

  cv_bucket_name = var.create_bucket ? aws_s3_bucket.cv_uploads[0].bucket : data.aws_s3_bucket.cv_uploads_existing[0].bucket
  cv_bucket_arn  = var.create_bucket ? aws_s3_bucket.cv_uploads[0].arn : data.aws_s3_bucket.cv_uploads_existing[0].arn
  cv_bucket_id   = var.create_bucket ? aws_s3_bucket.cv_uploads[0].id : data.aws_s3_bucket.cv_uploads_existing[0].id
}

provider "aws" {
  region = var.aws_region
}

data "archive_file" "lambdas_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../src/lambdas"
  output_path = "${path.module}/artifacts/lambdas.zip"
}

resource "aws_s3_bucket" "cv_uploads" {
  count  = var.create_bucket ? 1 : 0
  bucket = var.bucket_name
}

data "aws_s3_bucket" "cv_uploads_existing" {
  count  = var.create_bucket ? 0 : 1
  bucket = var.bucket_name
}

resource "aws_dynamodb_table" "cv_records" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "cv_id"

  attribute {
    name = "cv_id"
    type = "S"
  }
}

resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:HeadObject",
          "s3:PutObject"
        ],
        Resource = "${local.cv_bucket_arn}/*"
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem"
        ],
        Resource = aws_dynamodb_table.cv_records.arn
      }
    ]
  })
}

resource "aws_lambda_function" "process_cv" {
  function_name    = local.process_cv_function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "process_cv.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  filename         = data.archive_file.lambdas_zip.output_path
  source_code_hash = data.archive_file.lambdas_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.cv_records.name
    }
  }
}

resource "aws_lambda_function" "get_cv" {
  function_name    = local.get_cv_function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "get_cv.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  filename         = data.archive_file.lambdas_zip.output_path
  source_code_hash = data.archive_file.lambdas_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.cv_records.name
    }
  }
}

resource "aws_lambda_function" "upload_cv_url" {
  function_name    = local.upload_cv_url_function_name
  role             = aws_iam_role.lambda_exec.arn
  handler          = "upload_cv_url.handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  filename         = data.archive_file.lambdas_zip.output_path
  source_code_hash = data.archive_file.lambdas_zip.output_base64sha256

  environment {
    variables = {
      CV_UPLOAD_BUCKET           = local.cv_bucket_name
      UPLOAD_URL_EXPIRES_SECONDS = "300"
    }
  }
}

resource "aws_lambda_permission" "allow_s3_invoke_process_cv" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.process_cv.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = local.cv_bucket_arn
}

resource "aws_s3_bucket_notification" "cv_upload_events" {
  bucket = local.cv_bucket_id

  lambda_function {
    lambda_function_arn = aws_lambda_function.process_cv.arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".txt"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke_process_cv]
}

resource "aws_apigatewayv2_api" "cv_api" {
  name          = "${var.project_name}-cv-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "get_cv_integration" {
  api_id                 = aws_apigatewayv2_api.cv_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_cv.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "upload_cv_url_integration" {
  api_id                 = aws_apigatewayv2_api.cv_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.upload_cv_url.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_cv_route" {
  api_id    = aws_apigatewayv2_api.cv_api.id
  route_key = "GET /cv/{id+}"
  target    = "integrations/${aws_apigatewayv2_integration.get_cv_integration.id}"
}

resource "aws_apigatewayv2_route" "upload_cv_url_route" {
  api_id    = aws_apigatewayv2_api.cv_api.id
  route_key = "POST /cv/upload"
  target    = "integrations/${aws_apigatewayv2_integration.upload_cv_url_integration.id}"
}

resource "aws_apigatewayv2_route" "upload_cv_url_route_fallback" {
  api_id    = aws_apigatewayv2_api.cv_api.id
  route_key = "POST /cv/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.upload_cv_url_integration.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.cv_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "allow_apigw_invoke_get_cv" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_cv.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cv_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_apigw_invoke_upload_cv_url" {
  statement_id  = "AllowExecutionFromAPIGatewayUploadCvUrl"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.upload_cv_url.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.cv_api.execution_arn}/*/*"
}
