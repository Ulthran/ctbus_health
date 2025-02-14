import boto3
import datetime
import json
import os
import re
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


def get_recent_diet_data(doc_id: str, credentials: str) -> dict[str, dict[str, str]]:
    """Extract and parse diet data from Google Sheets API for the last two weeks"""
    current_date = datetime.datetime.now()
    
    service_account_info = json.loads(credentials.replace("'", '"'))
    SCOPES = ["https://www.googleapis.com/auth/documents"]
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("docs", "v1", credentials=credentials)

    result = (
        service.documents()
        .get(documentId=doc_id)
        .execute()
    )
    
    content = result['body']['content']
    diet_dict = {}
    current_date = None
    
    for item in content:
        if 'paragraph' in item:
            elements = item['paragraph'].get('elements', [])
            for element in elements:
                if 'textRun' in element:
                    text = element['textRun']['content'].strip()
                    
                    # Check if the line is a date (MM/DD/YY format)
                    if re.match(r'\d{2}/\d{2}/\d{2}', text):
                        current_date = text
                        diet_dict[current_date] = {}
                    
                    # Check if the line is a time-based entry (HH:MM - description)
                    elif re.match(r'\d{1,2}:\d{2} - ', text):
                        time, details = text.split(' - ', 1)
                        if current_date:
                            diet_dict[current_date][time] = details

    return diet_dict


def lambda_handler(event, context):
    try:
        diet_data = get_recent_diet_data(os.environ["DOC_ID"], google_credentials)

        return {
            "statusCode": 200,
            "body": json.dumps(diet_data),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
