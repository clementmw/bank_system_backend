from django.urls import path, include
from rest_framework_simplejwt.views import (TokenRefreshView,TokenVerifyView)
from .views import *


urlpatterns = [
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify')
]