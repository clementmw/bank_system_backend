from django.urls import path, include
from rest_framework_simplejwt.views import (TokenRefreshView,TokenVerifyView)
from .views import *



urlpatterns = [
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('register/', RegisterView.as_view(), name='Customer registeration'),
    path('verify/email/', VerifyEmailView.as_view(), name='verify-email'),
    path('login/customer/', CustomerLoginView.as_view(), name = "login customer" ),
    path('kyc/', handleKYC.as_view(), name='kyc upload'),
    path('logout/', handleLogoutView.as_view(), name='logout'),
    path('forget-password/', ForgetpasswordView.as_view(), name='forget password'),
    path('confirm-otp/', ConfirmOtpView.as_view(), name='confirm otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset password'),
    
    # Employees Routes
    path('login/staff/', StaffLoginView.as_view(), name='staff login'),
    path('logout/staff/', StaffLogoutView.as_view(), name='staff logout'),
    path('employee/creation/', HandleEmployeeAccount.as_view(), name='employee account creation'),
    


]