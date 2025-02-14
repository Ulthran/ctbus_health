import json
import os
import boto3
import psycopg2
from psycopg2 import sql

sqs_client = boto3.client("sqs")
secrets_client = boto3.client("secretsmanager")
bedrock_client = boto3.client("bedrock-runtime")

SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]

def get_db_credentials():
    secret_value = secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
    secret = json.loads(secret_value['SecretString'])
    return secret['username'], secret['password']

def lambda_handler(event, context):
    username, password = get_db_credentials()

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=5432,
            dbname=DB_NAME,
            user=username,
            password=password
        )
        cursor = conn.cursor()

        for record in event["Records"]:
            message = json.loads(record["body"])
            cursor.execute(
                sql.SQL("INSERT INTO weight (date, weight) VALUES (%s, %s)"),
                (message["id"], message["value"], message["timestamp"])
            )

        conn.commit()
        cursor.close()
        conn.close()

        for record in event["Records"]:
            sqs_client.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=record["receiptHandle"]
            )

        return {"statusCode": 200, "body": "Data inserted successfully"}

    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
