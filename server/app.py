#app
import os

from flask_jwt_extended import JWTManager,jwt_required,get_jwt_identity
from models import User,Account,Transaction,db,Reviews, Contact,TokenBlocklist,MpesaTransaction
from flask_migrate import Migrate
from flask import Flask,make_response,jsonify,request,render_template
from flask_cors import CORS
from flask_restful import Api,Resource
from flask_bcrypt import Bcrypt
from werkzeug.exceptions import NotFound
from auth import auth_bp
from users import user_bp
import random
from flask_mail import Mail
import requests
from requests.auth import HTTPBasicAuth
import base64
import datetime
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from views import UserAdminView,AccountAdminView,TransactionAdminView



app = Flask(
    __name__,
    static_url_path='',
    static_folder='../client/build',
    template_folder='../client/build'
    )

admin = Admin(app, name='My Admin Panel', template_mode='bootstrap4',url="/admin")

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 24 * 60 * 60
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bank.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI') #render database url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')


app.json.compact = False

VALID_API_KEYS=os.getenv ("VALID_API_KEYS")

db.init_app(app)
migrate = Migrate(app,db)
api=Api(app)
bcrypt = Bcrypt(app)
CORS(app) #connect frontend 
jwt = JWTManager()
jwt.init_app(app)
mail = Mail(app)

# add the admin dashboard views
admin.add_view(UserAdminView(User, db.session))
admin.add_view(AccountAdminView(Account, db.session))
admin.add_view(TransactionAdminView(Transaction, db.session))

# to add them to .env
consumer_key=os.getenv('CONSUMER_KEY')
cunsumer_secret=os.getenv('CONSUMER_SECRET')


app.register_blueprint(auth_bp, url_prefix='/v1.0/auth')
# app.register_blueprint(user_bp, url_prefix='/v1.0/user')

#additional claims
@jwt.additional_claims_loader
def make_additional_claims(identity):
    if identity == 'user1':
        return {"is_staff": True}
    return{"is_staff": False}

# ensure routes are accessed using apikeys
def require_api_key(f):
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return jsonify({"message": "Internal Server Error"}), 500
        if api_key not in VALID_API_KEYS:
            return jsonify({"message": "Internal Server Error"}), 500
        return f(*args, **kwargs)
    return decorated_function       

@app.route("/")
def index():
    """Home page."""""
    return "<h3>Evergreen Bank</h3>"

# jwt error handler
@jwt.expired_token_loader
def expired_token(jwt_header,jwt_data):
    return jsonify({'message': 'The token has expired.','error':'token expired'}), 401

@jwt.invalid_token_loader
def invalid_token(error):
    return jsonify({'message': 'Does not contain a valid token.','error':'invalid token'}), 401

@jwt.unauthorized_loader
def missing_token(error):
    return jsonify({'message': 'Request does not contain an access token.', 'error':'token missing'}), 401


@jwt.token_in_blocklist_loader #check if the jwt is revocked
def token_in_blocklist(jwt_header,jwt_data):
    jti = jwt_data['jti']

    token = db.session.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).scalar()
# if token is none : it will return false 
    return token is not None


@app.errorhandler(NotFound)
def handle_not_found(e):
    return render_template('index.html', title='Homepage', message='Welcome to our website!')

    

class CreateAccount(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()

        if not user:
            return {'message': 'User not found'}, 404

        accounts = Account.query.filter(Account.user_id == user.id).all()
        account = [a.serialize() for a in accounts]
        if not account:
            return {'message': 'Account not found for the specified user'}, 404

        response = make_response(jsonify(account), 200)
        return response

    @jwt_required()
    def post(self):
        data = request.get_json()
        current_user = get_jwt_identity()  
        user = User.query.filter_by(username=current_user).first()
        if not user:
            return {'message': 'User not found'}, 404
        else:
            account_number = ''.join(str(random.randint(0, 9)) for _ in range(10))
            account_type = data['account_type']
            balance = data.get('balance', 1000)
            
            newaccount = Account(account_type=account_type,account_number=account_number,balance=balance,user_id=user.id)
            db.session.add(newaccount)
            db.session.commit()

            response = make_response(jsonify(newaccount.serialize()), 200)
            return response
        
    @jwt_required()
    def patch(self):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        if not user:
            return {'message': 'User not found'}, 404
        else:
            account = Account.query.filter_by(user_id=user.id).first()
            if not account:
                return {'message': 'Account not found for the specified user'}, 404
            else:
                data = request.get_json()
                account_type = data['account_type']
                account.account_type = account_type
                db.session.commit()
                response = make_response(jsonify(account.serialize()), 200)
                return response
              
api.add_resource(CreateAccount, '/v1.0/account')


class GetTransaction(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()  

        if not user:
            return {'message': 'User not found'}, 404

        transactions = Transaction.query.filter_by(user_id=user.id).all()

        if not transactions:
            return {'message': 'No transactions found for this user'}, 404

        response = make_response(jsonify([transaction.serialize() for transaction in transactions]), 200)
        return response

class GetTransaction(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()  
        if not user:
            return {'message': 'User cannot be found '}, 404
       
        transactions = Transaction.query.filter_by(user_id=user.id).all()
        if not transactions:
            return {'message': 'No transaction found for this user'}, 404
        else:
            transaction = [t.serialize() for t in transactions]
            response = make_response(jsonify(transaction), 200)
            return response
      
    @jwt_required()
    def post(self):
        data = request.get_json()
        current_user = get_jwt_identity()
        amount = data.get('amount')
        transaction_type = data.get('transaction_type')

        user = User.query.filter_by(username=current_user).first()
        if not user:
            return {'message': 'User not found'}, 404

        account_number = data.get('account_number')
        if not account_number:
            return {'message': 'Account number is required'}, 400

        # Fetch the account associated with the current user and account number
        account = Account.query.filter_by(account_number=account_number, user_id=user.id).first()
        if not account:
            return {'message': 'Account not found for the specified user'}, 404

        # Check if the transaction type is 'deposit' and get receiver's account
        receiver_account_number = data.get('receiver_account_number')
        receiver_account = None
        if transaction_type == 'deposit' and receiver_account_number:
            receiver_account = Account.query.filter_by(account_number=receiver_account_number).first()
            if not receiver_account:
                return {'message': 'Receiver account not found'}, 404

        try:
            amount = int(amount)
        except ValueError:
            return {'message': 'Amount must be a valid integer'}, 400

        if amount < 0:
            return {'message': 'Amount must be non-negative'}, 400
        
        if transaction_type not in ('withdraw', 'deposit'):
            return {'message': 'Invalid transaction type'}, 400

        if transaction_type == 'withdraw' and amount > account.balance:
            return {'message': 'Insufficient funds'}, 400
        
        if transaction_type == 'withdraw':
            account.balance -= amount
        elif transaction_type == 'deposit':
            if account.balance < amount:
                return {'message': 'Cannot transfer funds, insufficient balance'}, 400
            account.balance -= amount
            receiver_account.balance += amount
        
        # Automatically populate receiver details if it's a deposit
        receiver = receiver_account.user if receiver_account else None

        # Create a new transaction record
        new_transaction = Transaction(
            amount=amount,
            transaction_type=transaction_type,
            receiver_id=receiver.id if receiver else None,
            user_id=user.id,
            account_id=account.id
        )
        db.session.add(new_transaction)
        db.session.commit()

        # Prepare response data
        response_data = {
            "transaction": new_transaction.serialize(),
            "balance": account.balance
        }

        if receiver:
            response_data["receiver"] = {
                "firstName": receiver.firstName,
                "lastName": receiver.lastName,
                "AccountNo":receiver_account_number,
                "email": receiver.email
            }

        response = make_response(jsonify(response_data), 200)
        return response



api.add_resource(GetTransaction, '/v1.0/transaction')

class ReviewList(Resource):
    def get(self):
        get_reviews = [review.serialize() for review in Reviews.query.all()]
        response = make_response(jsonify(get_reviews), 200)
        return response
api.add_resource(ReviewList, '/reviews')

class ContactList(Resource):
    def post(self):
        data = request.get_json()
        full_name = data['full_name']
        email = data['email']
        message = data['message']

        new_contact = Contact(full_name=full_name, email=email, message=message)
        db.session.add(new_contact)
        db.session.commit()

        response = make_response(jsonify(new_contact.serialize()), 200)
        return response
    
api.add_resource(ContactList, '/v1.0/contact')

class UserList(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        if not user:
            return {'message': 'User not found'}, 404
        response = make_response(jsonify(user.serialize()), 200)
        return response
    
    @jwt_required()
    def patch(self):
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        if not user:
            return {'message': 'User not found'}, 404
        else:
            data = request.get_json()
            firstName = data['firstName']
            lastName = data['lastName']
            phone_number = data['phone_number']
            user.firstName = firstName
            user.lastName = lastName
            user.phone_number = phone_number
            db.session.commit()
            response = make_response(jsonify(user.serialize()), 200)
            return response

api.add_resource(UserList, '/v1.0/user')

## ---------------------------------------------------- consume daraja api ------------------------------------- ##
def generate_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, cunsumer_secret))
    if response.status_code==200:
        data = response.json()
        access_token = data['access_token']
        # expires_in = data['expires_in']
        return access_token
    return None

# function to  get the access token 
class Generate_token(Resource):
    def get(self):
        try:
            access_token= generate_token()
            if access_token:
                return {'access_token': access_token,
                        }, 200
            else:
                return {'message': 'Failed to generate access token'}, 500
        except Exception as e:
            return {'message': str(e)}, 500
        
api.add_resource(Generate_token, '/v1.0/generate_daraja_token')

# function for generating password for mpesa express(stk push)
def generate_password():
    short_code = "174379" ## to be changed depending with the business short code
    passkey = os.getenv("PASSKEY")   #to be added on dotenv
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    data_to_encode = short_code + passkey + timestamp
    encoded = base64.b64encode(data_to_encode.encode())

    return encoded.decode('utf-8'),timestamp

# mpesa express(stkpush)
def stk_push(amount,phone_number,user_id,account_id):
    token=generate_token()
    if not token:
        return {"error": "Failed to generate access token"}
    print(token)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    # print(Access_Token)

    password,timestamp = generate_password()

    payload={
        "BusinessShortCode": "174379",    
        "Password":password,    
        "Timestamp":timestamp,    
        "TransactionType": "CustomerPayBillOnline",    
        "Amount": amount,    
        "PartyA":phone_number,  # this is the customers phone number   
        "PartyB":"174379",    
        "PhoneNumber":phone_number,    
        "CallBackURL": "https://4210-2c0f-6300-204-e200-a566-9e2c-41f5-2e4f.ngrok-free.app/v1.0/mpesa_callback",  #after deployment replace with deployed url
        "AccountReference":"Test",    
        "TransactionDesc":"Test"
    }
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    response = requests.post(api_url, json=payload, headers=headers)
    # print(response.text)

    try:
        response_data = response.json()  # Attempt to parse JSON
    except ValueError:
        # Handle the case where response is not valid JSON
        return {"error": "Invalid JSON response from API", "content": response.text}

    # extract the data to save in the database
    merchant_request_id = response_data.get('MerchantRequestID')
    checkout_request_id = response_data.get('CheckoutRequestID')
    response_code = response_data.get('ResponseCode')
    response_description = response_data.get('ResponseDescription')
    customer_message = response_data.get('CustomerMessage')
    
    response_code = response_data.get('ResponseCode')
    if response_code == '0':    # save data in db if status is 0
        mpesa_transaction  = MpesaTransaction(
            amount=amount,
            mpesa_receipt_number = checkout_request_id,
            phoneNumber = phone_number,
            status = "Pending",
            description = response_description,
            user_id = user_id,
            account_id = account_id
        )
        db.session.add(mpesa_transaction)
        db.session.commit()

    return{
        "MerchantRequestID": merchant_request_id,
        "CheckoutRequestID": checkout_request_id,
        "ResponseCode": response_code,
        "ResponseDescription": response_description,
        "CustomerMessage": customer_message,
        "transaction":mpesa_transaction.serialize()
    }

    
@app.route('/v1.0/stkmpesa', methods=['POST'])
@jwt_required()
def pay():
    try:
        current_user = get_jwt_identity()
        user = User.query.filter_by(username=current_user).first()
        data = request.get_json()
        
        amount = data.get('amount')
        phone_number = data.get('phone_number')
        account_number = data.get('account_number')  # Assuming you're passing the account number

        account = Account.query.filter_by(account_number=account_number).first()
        if not account:
            return jsonify({"error": "Account not found"}), 404

        if amount and phone_number and account:
            user_id = user.id
            account_id = account.id  # Fetch the account ID to pass to the stk_push function
            
            response = stk_push(amount, phone_number, user_id, account_id)
            return jsonify(response)
        return jsonify({"error": "Missing required parameters"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# handle callback url from mpesa to update status
@app.route('/v1.0/mpesa_callback', methods=['POST'])
def mpesa_callback():
    try:
        data = request.get_json()
        print("Received Callback Data:", data)  # Debugging line
        
        # Safely access nested JSON data
        result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')

        print(f"Result Code: {result_code}, Checkout Request ID: {checkout_request_id}")  # Debugging line

        # Validate result_code and checkout_request_id
        if result_code is None or checkout_request_id is None:
            return jsonify({"error": "Invalid callback data"}), 400
        
        # Find transaction in the database
        transaction = MpesaTransaction.query.filter_by(mpesa_receipt_number=checkout_request_id).first()

        if transaction:
            if result_code == 0:  # Success
                transaction.status = 'Success'

                # Update account balance
                account = Account.query.get(transaction.account_id)
                if account:
                    account.balance += transaction.amount
                    
                    # Record the deposit transaction
                    new_transaction = Transaction(
                        user_id=transaction.user_id,
                        amount=transaction.amount,
                        transaction_type='deposit',
                        account_id=account.id,
                        description="Mpesa Stk push deposit",
                        # mpesa_receipt_number=data['Body']['stkCallback']['CallbackMetadata']['Item'][1]['Value']  # Add this line
                    )
                    db.session.add(new_transaction)
                    db.session.commit()
            else:  # Failed
                transaction.status = 'Failed'
            db.session.commit()

        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200
    
    except Exception as e:
        print(f"Error processing callback: {e}")  # Debugging line
        return jsonify({"error": str(e)}), 500

 

# business to customer :-withdraw to mpesa
def generate_secure_credentials():
    # to change secure credentials once registered in safaricom 
    secure_credentials = "OiQgQZTIkhL/wGkelvwMcNwNT50RjMNguwor2Vzqgrfcs+dh/ehN2J3BybvJVRAqz+dUwlTa7173ZVcmEOzf5Vuca1LIBIkh40N0SJIu9eApSjf4N5gqFCya4bFDNKCwswPSsp81syahXGbPX8xmkaFjbqtXf1OPWVbbNjpl0hcx3m88bHdVzQYDCfE6f4GgOmUlZSIYxtfp7KFZdndm8x3OR6NshF9GbEz3Z8PxOXGrbVcGGvZEuuuSSoYMAvN+hLIhRto3fk1eQuSqO0bwCvGZJhwcsR+C3O3A4FSmU1CaqNv8eLX0L5Fn4MA59OKPuLAMjrVmFuR2FZiKlMbnhg=="
    return secure_credentials


def withdraw_from_mpesa(amount, phone_number):
    token = generate_token()
    if not token:
        return {"Error":"Failed in generating access token"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload={          
        "OriginatorConversationID": "2d29071c-6e2a-4dc4-bc71-cbb1155748d2",
        "InitiatorName": "testapi",
        "SecurityCredential":generate_secure_credentials(),
        "CommandID":"BusinessPayment",
        "Amount":amount,
        "PartyA":"600996",
        "PartyB":phone_number,
        "Remarks":"here are my remarks",
        "QueueTimeOutURL":"https://mydomain.com/b2c/queue",
        "ResultURL":"https://mydomain.com/b2c/result",
        "Occassion":"Christmas"

    }

    api_url = "https://sandbox.safaricom.co.ke/mpesa/b2c/v3/paymentrequest"

    response = requests.post(api_url, json=payload, headers=headers)

    try:
        response_data = response.json()  # Attempt to parse JSON
        return response_data
    # Process the response data
    except ValueError:
        # Handle the case where response is not valid JSON
        return {"error": "Invalid JSON response from API", "content": response.text}
    

@app.route('/v1.0/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json()
    amount = data.get('amount')
    phone_number = data.get('phone_number')

    if amount and phone_number:
        response = withdraw_from_mpesa(amount, phone_number)
        return jsonify(response)
    return jsonify({"error": "Missing required parameters"}), 400
            
@app.route('/b2c/result', methods=['POST'])
def b2c_result():
    data = request.get_json()
    # Process the result data as needed
    print("B2C Result:", data)
    return jsonify({"ResultCode": 0, "ResultDesc": "Received"}), 200

@app.route('/b2c/timeout', methods=['POST'])
def b2c_timeout():
    data = request.get_json()
    # Process the timeout data as needed
    print("B2C Timeout:", data)
    return jsonify({"ResultCode": 0, "ResultDesc": "Timeout received"}), 200

        



    
















      

if __name__ == '__main__':
    app.run(port=5554, debug=True)



    # add role jwt -admin /admin
    # user -/user
    # introduce flask admin
    # pdf
    # introduce views **done**
    # introduce utility to handle mail
    # version control of api **done**
    # apikey headers **done**
    # add cloudinary to edit profile image
    # integrate mpesa sdk for deposit **done**