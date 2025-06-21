import os
import boto3
from dotenv import load_dotenv
from lambda_function import lambda_handler, DynamoDBClient

load_dotenv()


def create_local_table():
    if os.getenv("LOCAL_DYNAMODB") == "true":
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url="http://localhost:8000",
            region_name="us-east-1",
            aws_access_key_id="fake",
            aws_secret_access_key="fake",
        )
    else:
        dynamodb = boto3.resource("dynamodb")

    table_name = os.environ["DYNAMODB_TABLE"]

    try:
        table = dynamodb.Table(table_name)
        table.load()
        print(f"Table {table_name} already exists")
        return table
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        print(f"Creating table {table_name}...")

        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "date", "KeyType": "HASH"},
                {"AttributeName": "timestamp_device", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "date", "AttributeType": "S"},
                {"AttributeName": "timestamp_device", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        table.wait_until_exists()
        print(f"Table {table_name} created successfully")
        return table


def setup_local_aws():
    if os.getenv("LOCAL_DYNAMODB") == "true":
        os.environ["AWS_ACCESS_KEY_ID"] = "fake"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "fake"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        boto3.setup_default_session(
            aws_access_key_id="fake",
            aws_secret_access_key="fake",
            region_name="us-east-1",
        )

        original_resource = boto3.resource

        def local_dynamodb_resource(service_name, **kwargs):
            if service_name == "dynamodb":
                kwargs["endpoint_url"] = "http://localhost:8000"
            return original_resource(service_name, **kwargs)

        boto3.resource = local_dynamodb_resource


if __name__ == "__main__":
    setup_local_aws()
    create_local_table()

    print("Running temperature polling...")
    result = lambda_handler({}, {})
    print(f"Result: {result}")
