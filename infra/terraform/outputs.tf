output "s3_bucket_name" {
  value       = local.cv_bucket_name
  description = "S3 bucket where CV files are uploaded"
}

output "dynamodb_table_name" {
  value       = aws_dynamodb_table.cv_records.name
  description = "DynamoDB table for CV records"
}

output "process_cv_lambda_name" {
  value       = aws_lambda_function.process_cv.function_name
  description = "Lambda function triggered by S3 uploads"
}

output "get_cv_lambda_name" {
  value       = aws_lambda_function.get_cv.function_name
  description = "Lambda function used by API Gateway"
}

output "upload_cv_url_lambda_name" {
  value       = aws_lambda_function.upload_cv_url.function_name
  description = "Lambda function used to generate presigned upload URLs"
}

output "api_base_url" {
  value       = aws_apigatewayv2_api.cv_api.api_endpoint
  description = "HTTP API base URL for bonus endpoint"
}
