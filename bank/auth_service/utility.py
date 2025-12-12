import random
import string
import datetime
import uuid
from rest_framework import pagination
import secrets



def generate_otp():
    characters = string.digits
    otp = ''.join(random.choices(characters,k=6))
    # print(otp)
    return otp
    

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(char.islower() for char in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit"

    if not any(char in string.punctuation for char in password):
        return False, "Password must contain at least one special character"

    return True, None

def generate_employee_id():
    year = datetime.datetime.now().year
    id = f"EMP{year}" + str(uuid.uuid4())[:10].upper()

    # print(id)
    return id

def generate_customer_id():
    year = datetime.datetime.now().year
    id = f"CUST{year}" + str(uuid.uuid4())[:8].upper()

    return id


def generate_temporary_password(): 
    characters = string.ascii_letters + string.digits
    password = ''.join(random.choice(characters) for _ in range(12))
    # print(password)
    
    return password

class CustomPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50
    page_query_param = 'page'
