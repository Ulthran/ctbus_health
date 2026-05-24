import json
import os
import boto3
from botocore.exceptions import ClientError

BUCKET = os.environ["BUCKET_NAME"]
PREFIX = "diet/"

s3 = boto3.client("s3")

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json",
}


def lambda_handler(event, context):
    path = event.get("rawPath", "")

    if path.endswith("/diet/dates"):
        return _handle_dates()

    parts = path.rsplit("/", 1)
    date = parts[-1] if parts else ""
    if len(date) == 10 and date[4] == "-" and date[7] == "-":
        return _handle_day(date)

    return _resp(404, {"error": "Not found"})


def _handle_dates():
    dates = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json") and "/" not in key[len(PREFIX):]:
                date = key[len(PREFIX):-5]
                if len(date) == 10:
                    dates.append(date)
    dates.sort(reverse=True)
    return _resp(200, dates)


def _handle_day(date):
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=f"{PREFIX}{date}.json")
        data = json.loads(obj["Body"].read())
        return _resp(200, data)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return _resp(404, {"error": f"No data for {date}"})
        raise


def _resp(status, body):
    return {"statusCode": status, "headers": CORS, "body": json.dumps(body)}
