import json
import os
import unittest
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_process_cv_handler_module():
    module_path = PROJECT_ROOT / "src" / "lambdas" / "process_cv" / "handler.py"
    spec = spec_from_file_location("process_cv_handler", module_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


process_cv_handler = _load_process_cv_handler_module()


class _FakeBody:
    def __init__(self, content: bytes):
        self._content = content

    def read(self):
        return self._content


class _FakeS3Client:
    def __init__(self, content: str, size: int, etag: str):
        self._content = content
        self._size = size
        self._etag = etag
        self.get_object_calls = []
        self.head_object_calls = []

    def get_object(self, Bucket, Key):
        self.get_object_calls.append({"Bucket": Bucket, "Key": Key})
        return {"Body": _FakeBody(self._content.encode("utf-8"))}

    def head_object(self, Bucket, Key):
        self.head_object_calls.append({"Bucket": Bucket, "Key": Key})
        return {
            "ContentLength": self._size,
            "ETag": self._etag,
            "LastModified": datetime(2026, 2, 28, 10, 0, 0, tzinfo=timezone.utc),
        }


class _FakeTable:
    def __init__(self):
        self.put_items = []

    def put_item(self, Item):
        self.put_items.append(Item)


class _FakeDynamoResource:
    def __init__(self, table):
        self._table = table
        self.table_names = []

    def Table(self, table_name):
        self.table_names.append(table_name)
        return self._table


class _FakeLambdaContext:
    function_name = "process-cv"
    function_version = "$LATEST"
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:process-cv"
    memory_limit_in_mb = 128
    aws_request_id = "test-request-id"
    log_group_name = "/aws/lambda/process-cv"
    log_stream_name = "2026/02/28/[$LATEST]test"


class ProcessCvHandlerTests(unittest.TestCase):
    def setUp(self):
        os.environ["DYNAMODB_TABLE_NAME"] = "cv_records"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    def tearDown(self):
        os.environ.pop("DYNAMODB_TABLE_NAME", None)
        os.environ.pop("AWS_DEFAULT_REGION", None)

    def test_returns_400_for_non_txt_file(self):
        context = _FakeLambdaContext()
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "cv-uploads"},
                        "object": {"key": "cv/sample_cv.pdf"},
                    }
                }
            ]
        }

        response = process_cv_handler.handler(event, context)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["message"], "Only .txt files are supported")

    def test_processes_txt_and_persists_item(self):
        context = _FakeLambdaContext()
        long_text = "A" * 400
        fake_s3 = _FakeS3Client(content=long_text, size=400, etag='"abc123"')
        fake_table = _FakeTable()
        fake_dynamodb = _FakeDynamoResource(table=fake_table)

        def fake_boto3_client(service_name, **kwargs):
            self.assertEqual(service_name, "s3")
            return fake_s3

        def fake_boto3_resource(service_name, **kwargs):
            self.assertEqual(service_name, "dynamodb")
            return fake_dynamodb

        event = {
            "Records": [
                {
                    "eventTime": "2026-02-28T11:00:00Z",
                    "s3": {
                        "bucket": {"name": "cv-uploads"},
                        "object": {"key": "cv/sample_cv.txt"},
                    },
                }
            ]
        }

        with patch.object(process_cv_handler.boto3, "client", side_effect=fake_boto3_client), patch.object(
            process_cv_handler.boto3, "resource", side_effect=fake_boto3_resource
        ):
            response = process_cv_handler.handler(event, context)

        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["message"], "CV processed successfully")
        self.assertEqual(body["cv_id"], "sample_cv")
        self.assertEqual(body["table"], "cv_records")

        self.assertEqual(len(fake_table.put_items), 1)
        item = fake_table.put_items[0]

        self.assertEqual(item["cv_id"], "sample_cv")
        self.assertEqual(item["file_name"], "sample_cv.txt")
        self.assertEqual(item["file_size"], 400)
        self.assertEqual(item["uploaded_at"], "2026-02-28T11:00:00Z")
        self.assertEqual(item["summary_300"], "A" * 300)
        self.assertEqual(item["bucket"], "cv-uploads")
        self.assertEqual(item["object_key"], "cv/sample_cv.txt")
        self.assertEqual(item["etag"], "abc123")
        self.assertIn("created_at", item)


if __name__ == "__main__":
    unittest.main()
