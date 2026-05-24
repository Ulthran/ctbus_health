import os

ALLOWED = set(e.strip().lower() for e in os.environ["ALLOWED_EMAILS"].split(",") if e.strip())

def lambda_handler(event, context):
    email = event.get("request", {}).get("userAttributes", {}).get("email", "").lower()
    if email not in ALLOWED:
        raise Exception(f"Unauthorized: {email} is not on the access list")
    return event
