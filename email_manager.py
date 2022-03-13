import smtplib
import os

def send_email_notification(name:str, contact_email:str, contact_phone:str, message:str ):
    """
    sends email  message
    """
    MY_EMAIL = os.getenv('GMAIL_EMAIL')
    MY_PASSWORD = os.getenv('GMAIL_PASSWORD')
    TO_ADD = MY_EMAIL

    if MY_EMAIL is None or MY_PASSWORD is None:
        return False
    
    email = f"Subject:New Contact Message\n\nName:{name}\nEmail: {contact_email}\nPhone: {contact_phone}\nMessage: {message}"
    print('sending email message')
    try:
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=MY_EMAIL,password=MY_PASSWORD)
            connection.sendmail(from_addr=MY_EMAIL,
                                to_addrs=TO_ADD,
                                msg=email
                                )
    except smtplib.SMTPAuthenticationError as e:
        print(f'Error: {e}')
        return False
    except smtplib.SMTPNotSupportedError as e:
        print(f'Error: {e}')
        return False
    else:
        return True