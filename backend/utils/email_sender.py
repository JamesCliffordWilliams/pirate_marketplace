# Pirate Market - Forgot Password feature
# Added by Aniya Hopson 11/10/26
# Sends emails through Amazon SES

import os
import html
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

# SES client setup - uses the same IAM keys as S3
ses_client = boto3.client(
    "ses",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("SES_REGION", os.getenv("AWS_REGION", "us-east-2"))
)

SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL")


def send_password_reset_email(to_email, username, reset_link):
    """Sends the reset link. Returns True if SES accepted it and False if it didn't."""
    if not SENDER_EMAIL:
        print("SES error: SES_SENDER_EMAIL is not set")
        return False

    subject = "Reset your Pirate Market password"

    text_body = (
        f"Hi {username},\n\n"
        "We got a request to reset your Pirate Market password.\n"
        f"Open this link to choose a new one (it expires in 10 minutes):\n\n{reset_link}\n\n"
        "If you didn't ask for this, you can ignore this email. Your password won't change.\n\n"
        "- The Pirate Market Team"
    )

    safe_name = html.escape(username)
    html_body = f"""
    <p>Hi {safe_name},</p>
    <p>We got a request to reset your Pirate Market password.</p>
    <p><a href="{reset_link}">Choose a new password</a></p>
    <p>This link expires in 10 minutes. If you didn't ask for this, you can ignore this email.
       Your password won't change.</p>
    <p>- The Pirate Market Team</p>
    """

    try:
        ses_client.send_email(
            Source=f"Pirate Market <{SENDER_EMAIL}>",
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
            },
        )
        return True
    except ClientError as e:
        # SES answered but refused (not verified, no permission, etc.)
        print(f"SES send error: {e.response['Error']['Message']}")
        return False
    except BotoCoreError as e:
        # Couldn't reach SES at all (missing keys, no internet, wrong region name)
        print(f"SES connection error: {e}")
        return False