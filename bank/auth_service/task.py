from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings

# @shared_task
def send_verification_email(user_id):
    from auth_service.models import User  
    user = User.objects.get(id=user_id)

    # generate token
    token = user.generate_email_token()

    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}&uid={user.id}"
    
    print(verification_url)


def send_onboarding_email(user_id):
    pass

def send_new_kyc(kyc_id):
    pass

def send_employee_onboarding_email(employee_id):
    pass

def send_email_task(data):
    pass


