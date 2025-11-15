from django.urls import path, include
from rest_framework_simplejwt.views import (TokenRefreshView,TokenVerifyView)
from .views import *
from django.contrib.auth.views import LoginView
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('register/', RegisterView.as_view(), name='Customer registeration'),
    path('verify/email/', VerifyEmailView.as_view(), name='verify-email'),


]