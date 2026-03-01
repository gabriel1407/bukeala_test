import json
import os
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_upload_cv_handler_module():
    module_path = PROJECT_ROOT / "src" / "lambdas" / "upload_cv_url" / "handler.py"
    spec = spec_from_file_location("upload_cv_url_handler", module_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


upload_cv_url_handler = _load_upload_cv_handler_module()


class _FakeS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, Bucket, Key, Body, ContentType):
        self.calls.append(
            {
                "Bucket": Bucket,
                "Key": Key,
                "Body": Body,
                "ContentType": ContentType,
            }
        )


class _FakeLambdaContext:
    function_name = "upload-cv-url"
    function_version = "$LATEST"
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:upload-cv-url"
    memory_limit_in_mb = 128
    aws_request_id = "test-request-id"
    log_group_name = "/aws/lambda/upload-cv-url"
    log_stream_name = "2026/03/01/[$LATEST]test"


class UploadCvUrlHandlerTests(unittest.TestCase):
    def setUp(self):
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["CV_UPLOAD_BUCKET"] = "bukeala-buckets-test"

    def tearDown(self):
        os.environ.pop("AWS_DEFAULT_REGION", None)
        os.environ.pop("CV_UPLOAD_BUCKET", None)

    def test_returns_400_when_content_type_is_not_multipart(self):
        context = _FakeLambdaContext()
        event = {
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"cv_id": "gabriel"}),
            "isBase64Encoded": False,
        }

        response = upload_cv_url_handler.handler(event, context)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(response["headers"]["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(response["body"])["message"], "Content-Type must be multipart/form-data")

    def test_uploads_txt_file_from_form_data_and_returns_get_path(self):
        context = _FakeLambdaContext()
        fake_s3 = _FakeS3Client()
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        multipart_body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"cv_id\"\r\n\r\n"
            f"gabriel_cv\r\n"
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"gabriel_cv.txt\"\r\n"
            f"Content-Type: text/plain\r\n\r\n"
            f"Hello from form-data\r\n"
            f"--{boundary}--\r\n"
        )
        event = {
            "headers": {"content-type": f"multipart/form-data; boundary={boundary}"},
            "body": multipart_body,
            "isBase64Encoded": False,
        }

        with patch.object(upload_cv_url_handler.boto3, "client", return_value=fake_s3):
            response = upload_cv_url_handler.handler(event, context)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 202)
        self.assertEqual(response["headers"]["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(body["message"], "CV uploaded successfully")
        self.assertEqual(body["data"]["cv_id"], "gabriel_cv")
        self.assertEqual(body["data"]["object_key"], "cv/gabriel_cv.txt")
        self.assertEqual(body["data"]["file_name"], "gabriel_cv.txt")
        self.assertEqual(body["links"]["get_path"], "/cv/gabriel_cv")
        self.assertEqual(body["meta"]["status"], "accepted")

        self.assertEqual(len(fake_s3.calls), 1)
        self.assertEqual(fake_s3.calls[0]["Bucket"], "bukeala-buckets-test")
        self.assertEqual(fake_s3.calls[0]["Key"], "cv/gabriel_cv.txt")
        self.assertEqual(fake_s3.calls[0]["ContentType"], "text/plain")
        self.assertEqual(fake_s3.calls[0]["Body"], b"Hello from form-data")


if __name__ == "__main__":
    unittest.main()
