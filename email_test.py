import smtplib
import configparser
from email.mime.text import MIMEText


def test_smtp():
    # 1. Read configuration from .ini file
    config = configparser.ConfigParser()
    config.read('instance/config.ini')

    try:
        smtp_server = config.get('email', 'smtp_host')
        port = config.getint('email', 'smtp_port')
        user_email = config.get('email', 'smtp_user')
        app_password = config.get('email', 'smtp_password')
        recipient = config.get('email', 'recipient')
    except Exception as e:
        print(f"Error reading config.ini: {e}")
        return

    # 2. Prepare the test email
    # msg = MIMEText("This is a test email sent from Python to verify SMTP settings.")
    # msg['Subject'] = "SMTP Test Successful"
    # msg['From'] = user_email
    # msg['To'] = recipient



    # 3. Connect and send
    try:
        print(f"Connecting to {smtp_server}...")
        # Use Port 587 for TLS (recommended)
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()  # Secure the connection

        print("Logging in...")
        server.login(user_email, app_password)

        print("Sending test email...")
        server.send_message(msg)

        print("✅ SUCCESS: Test email sent successfully!")
        server.quit()

    except Exception as e:
        print(f"❌ FAILED: {e}")


if __name__ == "__main__":
    test_smtp()
