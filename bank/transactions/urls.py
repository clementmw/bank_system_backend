from django.urls import path,include
from .views import *

urlpatterns = [
    path('internal_transfer/',HandleInternalTransaction.as_view(),name="internal_transfer" ),
]
