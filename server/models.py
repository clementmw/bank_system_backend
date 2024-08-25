#models
from sqlalchemy_serializer import SerializerMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import validates
import re
from flask_bcrypt import Bcrypt 
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model,SerializerMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key = True)
    firstName = db.Column(db.String(100), nullable = False)
    lastName = db.Column(db.String(100), nullable = False)
    username = db.Column(db.String(20), nullable = False, unique = True)
    phone = db.Column(db.String, unique= True)
    email = db.Column(db.String,unique=True,nullable=False)
    address = db.Column(db.String,nullable=True)
    role = db.Column(db.String,default='user')
    hashed_password = db.Column(db.String, nullable = False)
    isActive = db.Column(db.Boolean, default=True)
    # relationship to account
    accounts = db.relationship('Account', backref='user')
    transactions = db.relationship('Transaction', backref='user', foreign_keys='Transaction.user_id')
    mpesa_transactions = db.relationship('MpesaTransaction', backref='user')
    created_at = db.Column(db.DateTime,server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    # validates email
    @validates('email')
    def validate_email(self, key, email):
        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'    
        if not re.match(email_pattern, email):
            raise ValueError('Invalid email format')
        
        return email
        
     # Password getter and setter methods
    @hybrid_property
    def password(self):
        return self.hashed_password

    @password.setter
    def password(self, plain_text_password):
        self.hashed_password = bcrypt.generate_password_hash(
            plain_text_password.encode('utf-8')).decode('utf-8')

    def check_password(self, attempted_password):
        return bcrypt.check_password_hash(self.hashed_password, attempted_password.encode('utf-8'))
        
    def serialize(self):
        return{
            'id':self.id,
            'firstname':self.firstName,
            'lastname':self.lastName,
            'username':self.username,
            'phone':self.phone,
            'email':self.email,
            'address':self.address,
            'role':self.role,
            'accounts': [account.serialize() for account in self.accounts],
            'transactions': [transaction.serialize() for transaction in self.transactions]
        }
    
    def __repr__ (self):
        return f"ID:{self.id} FirstName:{self.firstName}, LastName:{self.lastName},  Username:{self.username},  Email:{self.email}, Phone Number:{self.phone}"


class Account(db.Model,SerializerMixin):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key = True)
    account_type = db.Column(db.String)
    account_number = db.Column(db.Integer,unique=True)
    balance = db.Column(db.Integer)
    # relationship to user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # relationship to transaction
    transactions = db.relationship('Transaction', backref='account')
    mpesa_transactions = db.relationship('MpesaTransaction', backref='account')
    created_at = db.Column(db.DateTime,server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    def serialize(self):
        return{
            'account_type':self.account_type,
            'account_number':self.account_number,
            'balance':self.balance,
            'user':{
                'firstName':self.user.firstName,
                'lastName':self.user.lastName,
                'email':self.user.email,
                'address':self.user.address
            }

        }
    
class Transaction(db.Model,SerializerMixin):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key = True)
    amount = db.Column(db.Integer)
    # relationship to user and account
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    transaction_type = db.Column(db.String)  #deposit or withdraw
    description = db.Column(db.String)
    mpesa_receipt_number = db.Column(db.String)
    created_at = db.Column(db.DateTime,server_default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    def serialize(self):
        return{
            "id": self.id,
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "description": self.description,
            "account": {
                "account_number": self.account.account_number,
                "balance": self.account.balance,
            },
            "user": {
                "firstName": self.user.firstName,
                "email": self.user.email,
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

class Reviews(db.Model,SerializerMixin):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key = True)
    customer_name = db.Column(db.String)
    review = db.Column(db.String)
    rating = db.Column(db.Integer)

    def serialize(self):
        return {
            'id':self.id,
            'customer_name': self.customer_name,
            'review': self.review,
            'rating': self.rating
        }
class Contact(db.Model,SerializerMixin):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key = True)
    full_name = db.Column(db.String)
    email = db.Column(db.String)
    message = db.Column(db.String)

    # validate email 
    @validates('email')
    def validate_email(self, key, email):
        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        
        if not re.match(email_pattern, email):
            raise ValueError('Invalid email format')
        
        return email
    #serialize
    def serialize(self):
        return{
            'id':self.id,
            'full_name': self.full_name,
            'email': self.email,
            'message': self.message,
        }
    
# table to store the mpesa transaction
class MpesaTransaction(db.Model,SerializerMixin):
    __tablename__ = 'mpesa_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer)
    mpesa_receipt_number = db.Column(db.String)
    phoneNumber = db.Column(db.String)
    status = db.Column(db.String) #either failed completed, or pending
    transaction_date = db.Column(db.DateTime, server_default=db.func.now())
    description = db.Column(db.String)
    # relationship to the user and account
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

    def serialize(self):
        return{
            "id": self.id,
            "amount": self.amount,
            "mpesa_receipt_number": self.mpesa_receipt_number,
            "phoneNumber": self.phoneNumber,
            "status": self.status,
            "transaction_date": self.transaction_date,
            "description": self.description,
            'user':self.user.serialize(),
            'account':self.account.serialize()        
        }

class TokenBlocklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(), nullable=True)
    created_at = db.Column(db.DateTime , default=datetime.now())

    def __repr__ (self):
        return f"<tokem {self.jti}>"

 
