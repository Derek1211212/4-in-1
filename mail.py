import requests

def send_email_with_postmark(api_token, to_email, subject, body):
    url = "https://api.postmarkapp.com/email"
    headers = {
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": api_token
    }

    payload = {
        "From": "d.agyakwa@touton.com",  # Replace with your Postmark verified email address
        "To": to_email,
        "Subject": subject,
        "TextBody": body,
        "MessageStream": "outbound"  # Use "outbound" or "transactions" depending on the type of email
    }

    try:
        response = requests.post(url, json=payload, headers=headers)

        # Check if the email was sent successfully
        if response.status_code == 200:
            print(f"Email sent to {to_email}")
        else:
            print(f"Failed to send email. Status code: {response.status_code}, Error: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")

# Example usage
api_token = "15f586fa-bd12-4654-8c9c-cf8ace6f634d"  # Your Postmark API token
to_email = "derickbill3@gmail.com"  # Replace with recipient's email address
subject = "Road Worthy Certificate Expiry Notification"
body = """
Dear User,

This is a reminder that your roadworthy certificate is about to expire in 7 days. 
Please make sure to renew it before the expiration date.

Regards,
Your Vehicle Management System
"""

# Call the function to send the email
send_email_with_postmark(api_token, to_email, subject, body)
