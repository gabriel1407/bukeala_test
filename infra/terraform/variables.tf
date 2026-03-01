variable "aws_region" {
  description = "AWS region where resources will be deployed"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Base name used to prefix resources"
  type        = string
  default     = "bukeala"
}

variable "bucket_name" {
  description = "S3 bucket for CV uploads (existing or to create)"
  type        = string
  default     = "bukeala-buckets-test"
}

variable "create_bucket" {
  description = "Create S3 bucket with Terraform. Set false to use an existing bucket_name"
  type        = bool
  default     = false
}

variable "dynamodb_table_name" {
  description = "DynamoDB table for CV records"
  type        = string
  default     = "cv_records"
}
