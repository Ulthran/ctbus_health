import os
import json
import boto3
import psycopg2

secrets_client = boto3.client("secretsmanager")

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

        # Define schema
        schema_sql = """
        CREATE TABLE IF NOT EXISTS weight (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL UNIQUE,
            weight REAL NOT NULL CHECK (weight < 300 AND weight > 0) 
        );

        CREATE TABLE IF NOT EXISTS diet (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            time TIME NOT NULL,
            raw_description TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            fdc_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fdc (
            fdc_id INTEGER PRIMARY KEY,

        );
        """

        cursor.execute(schema_sql)
        conn.commit()
        cursor.close()
        conn.close()

        return {"statusCode": 200, "body": "Schema created successfully"}

    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
