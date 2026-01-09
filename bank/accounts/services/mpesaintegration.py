from django_daraja.mpesa.core import MpesaClient
from ..utility import *
from decouple import config
from rest_framework.response import Response
from rest_framework import status
import logging
import requests
import xml.etree.ElementTree as ET
from django.shortcuts import redirect
from django.http import HttpResponse
import json
from django.views.decorators.csrf import csrf_exempt


logger = logging.getLogger(__name__)

def initiate_stk_push(self):
        try:
            cl = MpesaClient()
            phone_number = "254705960166"
            amount = 10

            print("phone",phone_number)
            print("amount",amount)
            
            if not phone_number:
                return Response({"error": "Please provide phone number"}, status=status.HTTP_400_BAD_REQUEST)
            
            if not amount:
                return Response({"error": "Please provide amount"}, status=status.HTTP_400_BAD_REQUEST)
            
            # handle the phone number format
            if phone_number.startswith("0"):
                phone_number = '254' + phone_number[1:] 
            elif phone_number.startswith("+"):
                phone_number = phone_number[1:]

            # convert the amount to integer
            try:
                amount = int(float(amount))
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            

            # generate unque transaction 
            account_reference = "account_reference"
            transaction_desc = 'Payment for account opening'
            callback_url = config('MPESA_STK_CALLBACK_URL') 


            # initiate stk push 
            try:
                response = cl.stk_push(
                    phone_number=phone_number,
                    amount=amount,
                    account_reference=account_reference,
                    transaction_desc=transaction_desc,
                    callback_url=callback_url,
                )
            except Exception as e:
                logger.error(f"STK Push initiation failed: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # check if the response ois successfull

            if response.response_code == "0":
                # stk push initiated successfully

                ""
                {
                    "message": "stk push initiated successfully",
                    "checkout_request_id": "ws_CO_25042025011224490705960166",
                    "customer_message": "Success. Request accepted for processing",
                    "merchant_request_id": "75f4-4e91-aa3c-79e4611bbc5828498",
                    "response_code": "0",
                    "response_description": "Success. Request accepted for processing"
                }
                ""
                return {
                    "checkout_request_id":response.checkout_request_id,
                    "customer_message":response.customer_message,
                    "merchant_request_id":response.merchant_request_id,
                    "response_code":response.response_code,
                    "response_description":response.response_description
                }
            

        
        except Exception as e:
            logger.error(f"Unexpected error in initiate_stk_push: {str(e)}")
            return {"success": False, "error": str(e)}
        

@csrf_exempt
def safaricom_stk_callback(request):
    try:
        callback_data = json.loads(request.body)
        logger.info(f"M-Pesa callback received: {callback_data}")
        
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        checkout_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
        
        if result_code == 0:
            # Payment was successful
            logger.info(f"Payment successful for CheckoutRequestID: {callback_data}")
            # Process the payment details as needed
            return HttpResponse(status=200)
        else:
            # Payment failed or was cancelled
            logger.warning(f"Payment failed or cancelled for CheckoutRequestID: {checkout_id} with ResultCode: {result_code}, {callback_data}")
            return HttpResponse(status=200)
        

    except Exception as e:
        logger.error(f"Error parsing M-Pesa callback data: {str(e)}")
        return HttpResponse(status=400)


def businessTocustomer(self):
    try:
        cl = MpesaClient()
        """
        { 
                "OriginatorConversationID": "600997_Test_32et3241ed8yu", 
                "InitiatorName": "testapi", 
                "SecurityCredential": "RC6E9WDxXR4b9X2c6z3gp0oC5Th ==", 
                "CommandID": "BusinessPayment", 
                "Amount": "10", 
                "PartyA": "600992", 
                "PartyB": "254705912645", 
                "Remarks": "remarked", 
                "QueueTimeOutURL": "https://mydomain.com/path", 
                "ResultURL": "https://mydomain.com/path", 
                "Occassion": "ChristmasPay" 
            }

            response

            { 
                "ConversationID": "AG_20240706_20106e9209f64bebd05b", 
                "OriginatorConversationID": "600997_Test_32et3241ed8yu", 
                "ResponseCode": "0", 
                "ResponseDescription": "Accept the service request successfully." 
            }
        """
        try:
            response = cl.b2c_payment(
                amount=10,
                callback_url=config('MPESA_B2C_CALLBACK_URL'),
                command_id='BusinessPayment',
                transaction_desc='Business to customer payment',
                occassion='TestPayment',
                phone_number = "254705912645"

            )
        except Exception as e:
            logger.error(f"Business to customer payment failed: {str(e)}")
            return {"error": str(e)} 
       
        if response.response_code == "0":
            logger.info(f"Business to customer payment initiated successfully, {response}")
            return {
                "message": "Business to customer payment initiated successfully",
                "conversation_id":response.conversation_id,
                "originator_conversation_id":response.originator_conversation_id,
                "response_code":response.response_code,
                "response_description":response.response_description
            }


    
    except Exception as e:
        logger.error(f"Unexpected error in businessTocustomer: {str(e)}")
        return {"success": False, "error": str(e)}
    

@csrf_exempt
def safaricom_b2c_callback(request):
    try:
        data = json.loads(request.body)
        result = data.get("Result", {})

        result_code = result.get("ResultCode")
        result_desc = result.get("ResultDesc")
        conversation_id = result.get("ConversationID")
        transaction_id = result.get("TransactionID")

        if result_code == 0:
            logger.info(f"B2C payment successful: {transaction_id}")
        else:
            logger.warning(
                f"B2C payment failed: {result_code} - {result}"
            )

        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    except Exception as e:
        logger.error(f"B2C callback error: {str(e)}")
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
