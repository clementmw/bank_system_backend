import random
import string
import datetime
import uuid
from rest_framework import pagination



def generate_otp():
    pass

def validate_password_strength(password):
    pass

def generate_employee_id():
    year = datetime.datetime.now().year
    id = f"EMP{year}" + str(uuid.uuid4())[:10].upper()

    # print(id)
    return id

def generate_customer_id():
    year = datetime.datetime.now().year
    id = f"CUST{year}" + str(uuid.uuid4())[:8].upper()

    return id



def generate_account_number():
    pass

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
