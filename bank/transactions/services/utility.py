import uuid
import json
import hashlib
from datetime import datetime



# def generate_idempotency_key(user_id, account_no, amount):
#     """
#     Generate a unique idempotency key based on user, transaction, amount
#     """
#     key_components = f"{user_id}:{account_no}:{amount}:{datetime.now().isoformat()}"
#     return hashlib.sha256(key_components.encode()).hexdigest()


def generate_transaction_ref():
    """
    Generate a unique transaction reference
    """
    return str(uuid.uuid4()).replace('-', '').upper()[:10]
