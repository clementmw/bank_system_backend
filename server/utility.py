# handel mail

class sendMail():
    def send_user_signup_mail(user,email):
        from app import mail
        subject = "Welcome to Evergreen Bank"
        body = f"Dear {user},\n\nThank you for registering on our Evergreen Bank. We extend our sincere gratitude to you for choosing Evergreen Bank as your financial institution of choice. Your decision to entrust us with your financial needs is truly appreciated.\n\nShould you require any assistance or have any inquiries, Please do not hesitate to reach out to us. Our dedicated team is here to provide you with the highest level of service and support.\n\n Best regards,\n Evergreen Bank Team"
        recipients = [email]
        mail.send_message(subject=subject, recipients=recipients, body=body)