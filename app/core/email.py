import httpx
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings


async def send_html_email_direct_smtp(to_email: str, subject: str, html_content: str):
    """
    Fallback: Mengirimkan email HTML langsung via SMTP (Zoho Mail).
    Digunakan ketika gateway-genkiddo tidak tersedia.
    """
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"\n[EMAIL SMTP] SMTP credentials not configured. Skipped sending email to {to_email}.\nSubject: {subject}\n")
        return False
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)
        
        # Connect to SMTP server with TLS
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        
        print(f"[EMAIL SMTP] Email successfully sent directly via SMTP to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL SMTP ERROR] Failed to send email via SMTP to {to_email}: {str(e)}")
        return False


async def send_html_email(to_email: str, subject: str, html_content: str):
    """
    Mengirimkan email HTML.
    Pertama mencoba via microservice gateway-genkiddo.
    Jika gagal, otomatis fallback ke direct SMTP.
    """
    # Attempt 1: Try gateway
    if settings.GATEWAY_URL:
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "X-API-Key": settings.GATEWAY_API_KEY
                }
                payload = {
                    "to_email": to_email,
                    "subject": subject,
                    "html_content": html_content,
                    "event_type": "transactional"
                }
                url = f"{settings.GATEWAY_URL}/api/emails/send"
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                
                if response.status_code in (200, 201):
                    print(f"[EMAIL SENDER] Email successfully queued via gateway to {to_email}")
                    return
                else:
                    print(f"[EMAIL SENDER WARN] Gateway returned status {response.status_code}: {response.text}")
                    print(f"[EMAIL SENDER] Falling back to direct SMTP...")
        except Exception as e:
            print(f"[EMAIL SENDER WARN] Gateway unreachable: {str(e)}")
            print(f"[EMAIL SENDER] Falling back to direct SMTP...")
    else:
        print(f"[EMAIL SENDER] GATEWAY_URL not configured. Using direct SMTP...")
    
    # Attempt 2: Direct SMTP fallback
    success = await send_html_email_direct_smtp(to_email, subject, html_content)
    if not success:
        print(f"[EMAIL SENDER ERROR] All email delivery methods failed for {to_email}")
