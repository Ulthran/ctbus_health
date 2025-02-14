import boto3
import datetime
import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account


# Retrieve the Google credentials from AWS SSM
# Needs to be done here because SecureString parameters are decrypted at runtime
# Kept outside the handler to avoid decrypting the same parameter multiple times
print("Retrieving Google credentials from SSM")
ssm = boto3.client("ssm")
google_credentials_param = os.environ["GOOGLE_CREDENTIALS_PARAM"]
google_credentials_response = ssm.get_parameter(
    Name=google_credentials_param, WithDecryption=True  # Decrypt the secure string
)
google_credentials = google_credentials_response["Parameter"]["Value"]
print("Google credentials retrieved from SSM")


sqs = boto3.client("sqs")
queue_url = sqs.get_queue_url(QueueName=os.environ["QUEUE_NAME"])["QueueUrl"]


def get_weight_data_for_year(
    sheet_id: str, credentials: str, year: str = datetime.datetime.now().strftime("%Y")
) -> dict[datetime.datetime, float]:
    """Extract and parse weight data from Google Sheets API for a given year"""
    service_account_info = json.loads(credentials.replace("'", '"'))
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("sheets", "v4", credentials=credentials)

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{year}!R2C1:R367C3")
        .execute()
    )

    rows = result.get("values", [])
    return {datetime.datetime.strptime(row[0], "%m%d%Y"): float(row[2]) for row in rows if len(row) == 3}


def get_recent_weight_data(sheet_id: str, credentials: str) -> dict[str, float]:
    """Extract and parse weight data from Google Sheets API for this and last year"""
    current_year = datetime.datetime.now().year
    last_year = current_year - 1
    data = get_weight_data_for_year(sheet_id, credentials, str(current_year))
    data.update(get_weight_data_for_year(sheet_id, credentials, str(last_year)))

    # Only add the last 7 days to the queue
    last_week = datetime.datetime.now() - datetime.timedelta(days=7)
    last_week_data = {k: v for k, v in data.items() if k > last_week}
    # Convert dates to ISO format for SQS message
    last_week_data = {k.strftime("%Y%m%d"): v for k, v in last_week_data.items()}

    return last_week_data


# Utility to manually create a credentials string from a JSON file
# Download from GCP console under service account
def json_credentials_to_str(cred_fp: str) -> str:
    """Convert a JSON credentials file to a string with single quoted fields"""
    with open(cred_fp, "r") as f:
        json_data = json.load(f)
        return json.dumps(json_data).replace('"', "'")


def lambda_handler(event, context):
    try:
        weight_data = get_recent_weight_data(os.environ["SHEET_ID"], google_credentials)

        # Send the data to the SQS queue
        for date, weight in weight_data.items():
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"id": date, "value": weight, "timestamp": datetime.datetime.now().isoformat()}),
            )

        return {
            "statusCode": 200,
            "body": json.dumps(weight_data),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
