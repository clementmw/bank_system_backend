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
        uid = request.query_params.get("uid")
        token = request.query_params.get("token")

        if not uid or not token:
            return Response({"error": "Invalid verification link"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=uid)

            if user.verify_email(token):
                return Response({"message": "Email verified successfully"},
                                 status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid or expired token"},
                                 status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"error": "User not found"},
                            status=status.HTTP_404_NOT_FOUND)

            
