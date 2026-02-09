from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string


def generate_otp():
    """Generate a secure 6-digit OTP code"""
    return ''.join(random.choices(string.digits, k=6))


def send_verification_email(user, request=None):
    """Send OTP verification email to user"""
    
    # Generate OTP
    otp = generate_otp()
    user.email_verification_otp = otp
    user.otp_created_at = timezone.now()
    user.save()
    
    # Email subject
    subject = 'Verify Your Email - CredentialPath'
    
    # Email context
    context = {
        'user_name': user.full_name,
        'otp_code': otp,
        'business_name': user.business_name or 'CredentialPath',
    }
    
    # Render HTML email
    html_content = render_to_string('emails/verify_email_otp.html', context)
    text_content = strip_tags(html_content)
    
    # Create email
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    # Send email
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def is_otp_valid(user):
    """Check if OTP is still valid (10 minutes expiry)"""
    if not user.otp_created_at:
        return False
    
    expiry_time = user.otp_created_at + timedelta(minutes=10)
    return timezone.now() < expiry_time


def send_welcome_email(user):
    """Send welcome email after successful verification"""
    
    subject = 'Welcome to CredentialPath!'
    
    context = {
        'user_name': user.full_name,
        'business_name': user.business_name or 'CredentialPath',
    }
    
    html_content = render_to_string('emails/welcome_email.html', context)
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False


def send_certificate_email(certificate, recipient_email):
    """Send certificate to recipient via email"""
    
    subject = f'Your Certificate - {certificate.course}'
    
    context = {
        'recipient_name': certificate.recipient,
        'course': certificate.course,
        'certificate_type': certificate.certificate_type,
        'issue_date': certificate.issue_date,
        'issuer_name': certificate.issuer_name,
        'verification_url': certificate.verification_link,
        'credential_id': certificate.credential_id,
        'certificate_no': certificate.certificate_no,
    }
    
    html_content = render_to_string('emails/certificate_email.html', context)
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending certificate email: {e}")
        return False


def send_password_reset_email(user, reset_link):
    """Send password reset email"""
    
    subject = 'Reset Your Password - CredentialPath'
    
    context = {
        'user_name': user.full_name,
        'reset_link': reset_link,
    }
    
    html_content = render_to_string('emails/password_reset.html', context)
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False
    

# Add this utility function to your utils.py or create a new notifications.py file

from .models import Notification

def create_notification(user, notification_type, title, message, certificate=None):
    """
    Create a notification for a user
    
    Args:
        user: User object
        notification_type: Type of notification (from Notification.NOTIFICATION_TYPES)
        title: Notification title
        message: Notification message
        certificate: Optional Certificate object
    
    Returns:
        Notification object
    """
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        certificate=certificate
    )
    return notification