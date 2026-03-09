from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300, rate_limit='10/m')
def send_email_task(self, recipient_email, subject, context, template_name, html_content=None):
    """
    Generic email sending task
    Args:
        recipient_email: Email address to send to
        subject: Email subject line
        context: Template context dictionary
        template_name: Path to HTML template
        html_content: Pre-rendered HTML (optional, overrides template_name)
    """
    try:
        from_email = settings.EMAIL_HOST_USER
        

        if not html_content:
            html_content = render_to_string(template_name, context)
            
        msg = EmailMultiAlternatives(subject, '', from_email, [recipient_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Email sent to {recipient_email}")
        return True
    
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_email}: {str(exc)}")
        raise self.retry(exc=exc)


@shared_task(queue="high", bind=True, max_retries=3, default_retry_delay=300)
def send_verification_email(self, user_id, URL):
    """Send email verification link to user"""
    try:
        from auth_service.models import User  
        user = User.objects.get(id=user_id)

        # Generate token
        token = user.generate_email_token()
        verification_url = f"{URL}/verify-email?token={token}&uid={user.id}"

        context = {
            'user': user.get_full_name(),
            'verification_url': verification_url,
        }
        logger.info(f"Attempting to send verification email to {verification_url}")
        
        # Send email directly (don't call another task)
        from_email = settings.EMAIL_HOST_USER
        html_content = render_to_string("Customer Emails/verification_email.html", context)
        
        msg = EmailMultiAlternatives(
            subject="Verify your email address",
            body='',
            from_email=from_email,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Verification email sent to {user.email}")
        return f"Verification email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
        raise
    except Exception as exc:
        logger.error(f"Error in send_verification_email task: {str(exc)}")
        raise self.retry(exc=exc)


@shared_task(queue="low", bind=True, max_retries=3, default_retry_delay=300)
def send_onboarding_email(self, user_id):
    """Send welcome/onboarding email to new user"""
    try:
        from auth_service.models import User  
        user = User.objects.get(id=user_id)

        context = {
            'user': user,
        }
        
        from_email = settings.EMAIL_HOST_USER
        html_content = render_to_string("Customer Emails/onboarding_email.html", context)
        
        msg = EmailMultiAlternatives(
            subject="Welcome to the Bank System!",
            body='',
            from_email=from_email,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Onboarding email sent to {user.email}")
        return f"Onboarding email sent to {user.email}"
        
    except Exception as exc:
        logger.error(f"Error in send_onboarding_email task: {str(exc)}")
        raise self.retry(exc=exc)

    
# @shared_task(queue="high", bind=True, max_retries=3, default_retry_delay=300)
# def send_new_kyc(self, kyc_id):
#     """Notify compliance team about new KYC submission"""
#     try:
#         from your_app.models import KYC  # Update with your actual KYC model path
#         kyc = KYC.objects.select_related('user').get(id=kyc_id)
        
#         context = {
#             'kyc': kyc,
#             'user': kyc.user,
#             'review_url': f"{settings.FRONTEND_URL}/admin/kyc/{kyc.id}"
#         }
        
#         from_email = settings.EMAIL_HOST_USER
#         html_content = render_to_string("Admin Emails/new_kyc_notification.html", context)
        
#         msg = EmailMultiAlternatives(
#             subject=f"New KYC Submission - {kyc.user.get_full_name()}",
#             body='',
#             from_email=from_email,
#             to=[settings.COMPLIANCE_EMAIL]  # Add this to your settings
#         )
#         msg.attach_alternative(html_content, "text/html")
#         msg.send()
        
#         logger.info(f"KYC notification sent for user {kyc.user.email}")
#         return f"KYC notification sent for {kyc.user.email}"
        
#     except Exception as exc:
#         logger.error(f"Error in send_new_kyc task: {str(exc)}")
#         raise self.retry(exc=exc)


@shared_task(queue="medium", bind=True, max_retries=3, default_retry_delay=300)
def send_employee_onboarding_email(self, employee_id):
    """Send onboarding email to new employee"""
    try:
        from auth_service.models import EmployeeProfile
        
        employee = EmployeeProfile.objects.select_related('user').get(id=employee_id)
        
        context = {
            'employee': employee,
            'portal_url': f"{settings.FRONTEND_URL}/employee/portal"
        }
        
        from_email = settings.EMAIL_HOST_USER
        html_content = render_to_string("Employee Emails/employee_onboarding.html", context)
        
        msg = EmailMultiAlternatives(
            subject="Welcome to the Bank System Team!",
            body='',
            from_email=from_email,
            to=[employee.user.email]  # Assuming employee has a user field
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        logger.info(f"Employee onboarding email sent to {employee.user.email}")
        return f"Employee onboarding email sent to {employee.user.email}"
        
    except Exception as exc:
        logger.error(f"Error in send_employee_onboarding_email task: {str(exc)}")
        raise self.retry(exc=exc)