import json
import os
import unittest
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_get_cv_handler_module():
    module_path = PROJECT_ROOT / "src" / "lambdas" / "get_cv" / "handler.py"
    spec = spec_from_file_location("get_cv_handler", module_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


get_cv_handler = _load_get_cv_handler_module()


class _FakeTable:
    def __init__(self, item=None):
        self._item = item
        self.get_item_calls = []

    def get_item(self, Key):
        self.get_item_calls.append(Key)
        if self._item is None:
            return {}
        return {"Item": self._item}


class _FakeDynamoResource:
    def __init__(self, table):
        self._table = table
        self.table_names = []

    def Table(self, table_name):
        self.table_names.append(table_name)
        return self._table


class _FakeLambdaContext:
    function_name = "get-cv"
    function_version = "$LATEST"
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:get-cv"
    memory_limit_in_mb = 128
    aws_request_id = "test-request-id"
    log_group_name = "/aws/lambda/get-cv"
    log_stream_name = "2026/02/28/[$LATEST]test"


class GetCvHandlerTests(unittest.TestCase):
    def setUp(self):
        os.environ["DYNAMODB_TABLE_NAME"] = "cv_records"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    def tearDown(self):
        os.environ.pop("DYNAMODB_TABLE_NAME", None)
        os.environ.pop("AWS_DEFAULT_REGION", None)

    def test_returns_400_when_id_is_missing(self):
        context = _FakeLambdaContext()
        event = {"pathParameters": None, "queryStringParameters": None}

        response = get_cv_handler.handler(event, context)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(response["headers"]["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(body["message"], "cv id is required")

    def test_returns_404_when_cv_not_found(self):
        context = _FakeLambdaContext()
        fake_table = _FakeTable(item=None)
        fake_dynamodb = _FakeDynamoResource(fake_table)

        with patch.object(get_cv_handler.boto3, "resource", return_value=fake_dynamodb):
            response = get_cv_handler.handler({"pathParameters": {"id": "missing_cv"}}, context)

        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(response["headers"]["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(body["message"], "CV not found")
        self.assertEqual(fake_table.get_item_calls, [{"cv_id": "missing_cv"}])

    def test_returns_200_when_cv_exists(self):
        context = _FakeLambdaContext()
        fake_item = {
            "cv_id": "sample_cv",
            "file_name": "sample_cv.txt",
            "file_size": Decimal("400"),
            "summary_300": "A" * 300,
        }
        fake_table = _FakeTable(item=fake_item)
        fake_dynamodb = _FakeDynamoResource(fake_table)

        with patch.object(get_cv_handler.boto3, "resource", return_value=fake_dynamodb):
            response = get_cv_handler.handler({"pathParameters": {"id": "sample_cv"}}, context)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Content-Type"], "application/json; charset=utf-8")

        body = json.loads(response["body"])
        self.assertEqual(body["message"], "CV retrieved successfully")
        self.assertEqual(body["data"]["cv_id"], "sample_cv")
        self.assertEqual(body["data"]["file_name"], "sample_cv.txt")
        self.assertEqual(body["data"]["file_size"], 400)

    def test_accepts_trailing_slash_in_id(self):
        context = _FakeLambdaContext()
        fake_item = {
            "cv_id": "sample_cv",
            "file_name": "sample_cv.txt",
            "file_size": Decimal("400"),
            "summary_300": "A" * 300,
        }
        fake_table = _FakeTable(item=fake_item)
        fake_dynamodb = _FakeDynamoResource(fake_table)

        with patch.object(get_cv_handler.boto3, "resource", return_value=fake_dynamodb):
            response = get_cv_handler.handler({"pathParameters": {"id": "sample_cv/"}}, context)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["data"]["cv_id"], "sample_cv")

    def test_returns_400_for_invalid_nested_id(self):
        context = _FakeLambdaContext()
        event = {"pathParameters": {"id": "folder/sample_cv"}}

        response = get_cv_handler.handler(event, context)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["message"], "invalid cv id format")


if __name__ == "__main__":
    unittest.main()
