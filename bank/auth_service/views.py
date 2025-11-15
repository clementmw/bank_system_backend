# will handle all authentication here .

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import *
from .models import *
from .task import *
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from django.db import transaction


logger = logging.getLogger(__name__)


def serialize_full_user(user):
    # Serialize basic user data
    user_data = UserSerializer(user).data
    
    # Get the role name from the ForeignKey relationship
    role_name = user.role.name  
    
    # Map role names to their respective profile serializers
    profile_serializers = {
        'STAFF': EmployeeProfileSerializer,
        'CUSTOMER': CustomerProfileSerializer,
        'ADMIN': EmployeeProfileSerializer,  # Assuming admin uses employee profile
    }
    
    # Get the appropriate serializer class for the role
    serializer_class = profile_serializers.get(role_name)
    
    if serializer_class:
        # Get the profile object based on role
        profile_obj = None
        if role_name == 'CUSTOMER':
            profile_obj = getattr(user, 'customer_profile', None)
        elif role_name in ['STAFF', 'ADMIN']:
            profile_obj = getattr(user, 'employee_profile', None)
        
        # Serialize profile data if exists
        if profile_obj:
            profile_data = serializer_class(profile_obj).data
            profile_data.pop('user', None)  # Remove nested user if exists
            user_data['profile'] = profile_data
        else:
            user_data['profile'] = None
    
    user_data['role_name'] = role_name
    
    return user_data

class RegisterView(APIView):

    def post(self,request):
        try:
            data = request.data

            email = data.get('email')
            password = data.get('password')
            phone_number = data.get('phone_number')
            address = data.get('address')

            if not email or not password or not phone_number:
                return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Block superuser/staff emails from being registered
            privileged_user = User.objects.filter(email__iexact=email, is_superuser=True).exists() \
                                or User.objects.filter(email__iexact=email, is_staff=True).exists()
            if privileged_user:
                # log the request
                logger.warning(f"Attempted registration with privileged email: {email} at {request.META.get('REMOTE_ADDR')}")
                
                return Response(
                    {"error": "Invalid email or password"},status=status.HTTP_401_UNAUTHORIZED)
            # confrim if email already exists
            if User.objects.filter(email=email).exists():
                return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)


            role = Role.objects.get(name="CUSTOMER")  # default role is customer
            
            with transaction.atomic():               
                serializer = UserSerializer(data={**request.data, "email":email, "role": role.id})
                if serializer.is_valid():
                    user = serializer.save()
                    user.is_active = False  # Deactivate user until email is verified
                    user.save()
                
                    
                    # Create CustomerProfile
                    CustomerProfile.objects.create(
                        user=user,
                        customer_id=generate_customer_id(),
                        phone_number=phone_number,
                        address=address
                    )
                    
                    # create kyc instance
                    KycProfile.objects.create(
                        user = user,
                        verification_status = "PENDING"
                    )
                    
                    logger.info(f"New user registered: {email} with role {role.name}")

                    # trigger email verification task
                    send_verification_email(user.id)
                    
                    return Response(
                        {
                            'message': 'User registered successfully',
                            'role':user.role.name,
                            # 'user': serialize_full_user(user)
                         },
                         
                        status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class VerifyEmailView(APIView):

    def get(self, request):
        try:
            uid = request.query_params.get("uid")
            token = request.query_params.get("token")

            if not uid or not token:
                return Response({"error": "Invalid verification link"},
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(id=uid)

                if user.verify_email(token):
                    # send onboarding email
                    # send_onboarding_email.delay(user.id)

                    return Response({"message": "Email verified successfully"},status=status.HTTP_200_OK)
                else:
                    return Response({"error": "Invalid or expired token"},
                                    status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({"error": "User not found"},
                                status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerLoginView(APIView):

    def post(self, request):
        try:
            data = request.data
            email = data.get("email")
            password = data.get("password")
            customer_id = data.get("customer_id")

            if not email or not password:
                return Response({"error": "Email and password are required"},status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(email=email) #might opt to login with customerid
                print(user.is_active)


                if not user.check_password(password):
                    return Response({"error": "Invalid email or password"},
                                    status=status.HTTP_401_UNAUTHORIZED)

                if user.role.name != "CUSTOMER":
                    return Response({"error": "Access denied. Not a customer."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)

                if not user.is_active:
                    return Response({"error": "Account is inactive. Please verify your email."}, #change to a more generic response 
                                    status=status.HTTP_403_FORBIDDEN)

                # check kyc verification status

                # if  user.kyc_profile.verification_status == "PENDING":
                #     return Response({"error": "Please upload KYC."}, status=status.HTTP_403_FORBIDDEN)
                
                # if not user.kyc_profile.verification_status == "VERIFIED":
                #     return Response({"error": "Account is not verified. Please upload KYC."}, 
                #                     status=status.HTTP_403_FORBIDDEN)

                refresh = RefreshToken.for_user(user)
                user_data = serialize_full_user(user)

                return Response({
                    "message": "Login successful",
                    "user": user_data,
                    "kyc_status": user.kyc_profile.verification_status,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }, status=status.HTTP_200_OK)

            except User.DoesNotExist:
                return Response({"error": "Invalid email or password"},status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class handleKYC(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user

            # ensure user is customer
            if user.role.name != "CUSTOMER":
                return Response({"error":"Access for kyc denied"}, status=status.HTTP_403_FORBIDDEN)

            
            document_type = request.data.get("doc_type")
            document_upload = request.FILES.get("file")
            id_no  = request.data.get("id_no")
            next_of_kin = request.data.get('kin_name')
            next_of_kin_contact = request.data.get('kin_contact')
            occupation = request.data.get('occupation')
            date_of_birth = request.data.get('dob')
            address = request.data.get('address')

            if not document_type and not document_upload:
                return Response({"error":"Documents needed"}, status=status.HTTP_404_NOT_FOUND)
            
            # pass the document to handle multiple documents
            


            
            with transaction.atomic():
                new_kyc =  KycProfile.objects.get(
                    user = user,
                )
                new_kyc.document_type = document_type
                new_kyc.document_upload = document_upload
                new_kyc.verification_status = "UPLOADED"
                new_kyc.save()

                # update customer profile
                customer_profile = CustomerProfile.objects.get(user=user)
                customer_profile.national_id = id_no
                customer_profile.next_of_kin_name = next_of_kin
                customer_profile.next_of_kin_contact = next_of_kin_contact
                customer_profile.occupation = occupation
                customer_profile.date_of_birth = date_of_birth
                customer_profile.address = address
                customer_profile.save()

                # notify admin of new application
                # send_new_kyc.delay(new_kyc.id)


                return Response({
                    "message":"KYC Uploaded successfully",

                },status = 200)
            
            return Response({"error":"Upload failed"}, status = 500)

        
        except Exception as e:
            return Response ({"error":str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class handleLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Successfully logged out."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)