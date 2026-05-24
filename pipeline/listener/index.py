import json
import os
import urllib.request
import boto3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

s3 = boto3.client("s3")
ssm = boto3.client("ssm")
sqs = boto3.client("sqs")

BUCKET = os.environ["BUCKET_NAME"]
QUEUE_URL = os.environ["QUEUE_URL"]

_cache = {}

def _get_param(name):
    if name not in _cache:
        _cache[name] = ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    return _cache[name]


def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
    if headers.get("x-telegram-bot-api-secret-token") != _get_param(os.environ["WEBHOOK_SECRET_PARAM"]):
        return {"statusCode": 403, "body": "Forbidden"}

    body = json.loads(event["body"])
    message = body.get("message", {})

    if not message:
        return {"statusCode": 200, "body": json.dumps({"ok": True})}

    message_id = message["message_id"]
    chat_id = message["chat"]["id"]
    utc_dt = datetime.fromtimestamp(message["date"], tz=timezone.utc)
    timestamp = utc_dt.isoformat()
    date_str = utc_dt.astimezone(ZoneInfo("America/New_York")).date().isoformat()

    raw_key = f"raw/telegram/{date_str}/{message_id}.json"
    s3.put_object(Bucket=BUCKET, Key=raw_key, Body=json.dumps(body), ContentType="application/json")

    photo_s3_key = None
    if "photo" in message:
        bot_token = _get_param(os.environ["BOT_TOKEN_PARAM"])
        file_id = message["photo"][-1]["file_id"]

        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        ) as resp:
            file_path = json.loads(resp.read())["result"]["file_path"]

        with urllib.request.urlopen(
            f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        ) as resp:
            photo_data = resp.read()

        ext = file_path.rsplit(".", 1)[-1]
        photo_s3_key = f"photos/{date_str}/{message_id}.{ext}"
        s3.put_object(Bucket=BUCKET, Key=photo_s3_key, Body=photo_data, ContentType="image/jpeg")

    text = message.get("text") or message.get("caption", "")

    payload = {
        "message_id": message_id,
        "chat_id": chat_id,
        "timestamp": timestamp,
        "date": date_str,
        "text": text,
        "raw_s3_key": raw_key,
    }
    if photo_s3_key:
        payload["photo_s3_key"] = photo_s3_key

    sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(payload))

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
