import json
import os
import uuid
import boto3

sqs = boto3.client("sqs")
QUEUE_URL = os.environ["QUEUE_URL"]

CORS_HEADERS = {
    "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": CORS_HEADERS, "body": ""}

    if method != "POST":
        return {"statusCode": 405, "headers": CORS_HEADERS, "body": "Method Not Allowed"}

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "Invalid JSON"})}

    source = body.get("source", "frontend")
    if source not in ("frontend", "recipe", "recipe_replace", "usage_event", "restaurant_lookup", "item_prefetch"):
        source = "frontend"

    client_id = body.get("client_id") or str(uuid.uuid4())

    if source == "recipe_replace":
        recipes = body.get("recipes")
        if not isinstance(recipes, list):
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "recipes list required"})}
        payload = {
            "source": "recipe_replace",
            "message_id": client_id,
            "client_id": client_id,
            "recipes": recipes,
        }
    elif source == "usage_event":
        payload = {
            "source": "usage_event",
            "message_id": client_id,
            "client_id": client_id,
            "event_type": body.get("event_type", "off_lookups"),
        }
    elif source == "restaurant_lookup":
        restaurant = body.get("restaurant", "").strip()
        if not restaurant:
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "restaurant required"})}
        payload = {
            "source": "restaurant_lookup",
            "message_id": client_id,
            "client_id": client_id,
            "restaurant": restaurant,
            "location": body.get("location", ""),
        }
    elif source == "item_prefetch":
        description = body.get("description", "").strip()
        if not description:
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "description required"})}
        payload = {
            "source": "item_prefetch",
            "message_id": client_id,
            "client_id": client_id,
            "description": description,
        }
    else:
        date = body.get("date")
        time_str = body.get("time", "00:00")
        items = body.get("items", [])
        if not date or not items:
            return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": "date and items required"})}
        payload = {
            "source": source,
            "message_id": client_id,
            "client_id": client_id,
            "timestamp": f"{date}T{time_str}:00",
            "date": date,
            "items": items,
        }
        if source == "recipe" and body.get("name"):
            payload["name"] = body["name"]

    sqs.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(payload))

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({"ok": True, "client_id": client_id}),
    }
