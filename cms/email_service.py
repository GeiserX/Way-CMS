"""
Email service for Way-CMS multi-tenant system.
Handles SMTP configuration and sending magic link emails.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


class EmailConfig:
    """Email configuration from environment variables."""
    
    @classmethod
    def get_config(cls) -> dict:
        return {
            'host': os.environ.get('SMTP_HOST', ''),
            'port': int(os.environ.get('SMTP_PORT', '587')),
            'user': os.environ.get('SMTP_USER', ''),
            'password': os.environ.get('SMTP_PASSWORD', ''),
            'from_email': os.environ.get('SMTP_FROM', ''),
            'from_name': os.environ.get('SMTP_FROM_NAME', 'Way-CMS'),
            'use_tls': os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
        }
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if email is properly configured."""
        config = cls.get_config()
        return bool(config['host'] and config['user'] and config['password'] and config['from_email'])


class EmailService:
    """Service for sending emails."""
    
    def __init__(self):
        self.config = EmailConfig.get_config()
    
    def send_email(self, to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> tuple[bool, str]:
        """
        Send an email.
        Returns: (success, error_message)
        """
        if not EmailConfig.is_configured():
            return False, 'Email is not configured. Please set SMTP environment variables.'
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.config['from_name']} <{self.config['from_email']}>"
            msg['To'] = to_email
            
            # Add text version (fallback)
            if text_body:
                msg.attach(MIMEText(text_body, 'plain'))
            
            # Add HTML version
            msg.attach(MIMEText(html_body, 'html'))
            
            # Connect and send
            if self.config['use_tls']:
                server = smtplib.SMTP(self.config['host'], self.config['port'])
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config['host'], self.config['port'])
            
            server.login(self.config['user'], self.config['password'])
            server.send_message(msg)
            server.quit()
            
            return True, ''
        
        except smtplib.SMTPAuthenticationError:
            return False, 'SMTP authentication failed. Check your credentials.'
        except smtplib.SMTPConnectError:
            return False, f"Could not connect to SMTP server {self.config['host']}:{self.config['port']}"
        except Exception as e:
            return False, f'Failed to send email: {str(e)}'
    
    def send_magic_link(self, to_email: str, magic_link_url: str, user_name: Optional[str] = None) -> tuple[bool, str]:
        """Send a magic link email to a user."""
        
        greeting = f"Hi {user_name}," if user_name else "Hi,"
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .logo {{ font-size: 28px; font-weight: bold; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 20px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
        .button:hover {{ opacity: 0.9; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; }}
        .link {{ word-break: break-all; color: #667eea; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Way-CMS</div>
        <p>{greeting}</p>
        <p>Click the button below to log in to Way-CMS. This link will expire in 24 hours.</p>
        <a href="{magic_link_url}" class="button">Log in to Way-CMS</a>
        <p>Or copy and paste this link into your browser:</p>
        <p class="link">{magic_link_url}</p>
        <div class="footer">
            <p>If you didn't request this email, you can safely ignore it.</p>
            <p>This link can only be used once and expires in 24 hours.</p>
        </div>
    </div>
</body>
</html>
"""
        
        text_body = f"""
{greeting}

Click the link below to log in to Way-CMS:

{magic_link_url}

This link will expire in 24 hours and can only be used once.

If you didn't request this email, you can safely ignore it.
"""
        
        return self.send_email(to_email, 'Your Way-CMS Login Link', html_body, text_body)
    
    def send_welcome_email(self, to_email: str, magic_link_url: str, user_name: Optional[str] = None, 
                          project_names: Optional[list] = None) -> tuple[bool, str]:
        """Send a welcome email to a new user with their magic link."""
        
        greeting = f"Hi {user_name}," if user_name else "Hi,"
        
        projects_html = ""
        if project_names:
            projects_list = "".join([f"<li>{name}</li>" for name in project_names])
            projects_html = f"""
        <p>You have been granted access to the following project(s):</p>
        <ul>{projects_list}</ul>
"""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .logo {{ font-size: 28px; font-weight: bold; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 20px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; }}
        .link {{ word-break: break-all; color: #667eea; }}
        ul {{ margin: 10px 0; padding-left: 20px; }}
        li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Way-CMS</div>
        <p>{greeting}</p>
        <p>Welcome to Way-CMS! Your account has been created.</p>
        {projects_html}
        <p>Click the button below to log in and get started:</p>
        <a href="{magic_link_url}" class="button">Log in to Way-CMS</a>
        <p>Or copy and paste this link into your browser:</p>
        <p class="link">{magic_link_url}</p>
        <div class="footer">
            <p>After logging in, you can optionally set a password for future logins.</p>
            <p>This link expires in 24 hours and can only be used once.</p>
        </div>
    </div>
</body>
</html>
"""
        
        projects_text = ""
        if project_names:
            projects_text = "\nYou have access to: " + ", ".join(project_names) + "\n"
        
        text_body = f"""
{greeting}

Welcome to Way-CMS! Your account has been created.
{projects_text}
Click the link below to log in:

{magic_link_url}

After logging in, you can optionally set a password for future logins.
This link expires in 24 hours and can only be used once.
"""
        
        return self.send_email(to_email, 'Welcome to Way-CMS', html_body, text_body)
    
    def test_connection(self) -> tuple[bool, str]:
        """Test the SMTP connection without sending an email."""
        if not EmailConfig.is_configured():
            return False, 'Email is not configured. Please set SMTP environment variables.'
        
        try:
            if self.config['use_tls']:
                server = smtplib.SMTP(self.config['host'], self.config['port'])
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.config['host'], self.config['port'])
            
            server.login(self.config['user'], self.config['password'])
            server.quit()
            
            return True, 'Connection successful'
        
        except smtplib.SMTPAuthenticationError:
            return False, 'SMTP authentication failed'
        except smtplib.SMTPConnectError:
            return False, f"Could not connect to {self.config['host']}:{self.config['port']}"
        except Exception as e:
            return False, str(e)


# Singleton instance
_email_service = None

def get_email_service() -> EmailService:
    """Get the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

