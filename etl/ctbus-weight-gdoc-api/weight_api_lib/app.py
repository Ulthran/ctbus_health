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


def get_weight_data_for_year(
    sheet_id: str, credentials: str, year: str = datetime.datetime.now().strftime("%Y")
) -> dict[str, float]:
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
    return {row[0]: float(row[2]) for row in rows if len(row) == 3}


def get_recent_weight_data(sheet_id: str, credentials: str) -> dict[str, float]:
    """Extract and parse weight data from Google Sheets API for this and last year"""
    current_year = datetime.datetime.now().year
    last_year = current_year - 1
    data = get_weight_data_for_year(sheet_id, credentials, str(current_year))
    data.update(get_weight_data_for_year(sheet_id, credentials, str(last_year)))
    return data


# Utility to manually create a credentials string from a JSON file
# Download from GCP console under service account
def json_credentials_to_str(cred_fp: str) -> str:
    """Convert a JSON credentials file to a string with single quoted fields"""
    with open(cred_fp, "r") as f:
        json_data = json.load(f)
        return json.dumps(json_data).replace('"', "'")


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps(
            get_recent_weight_data(os.environ["SHEET_ID"], google_credentials)
        ),
    }
