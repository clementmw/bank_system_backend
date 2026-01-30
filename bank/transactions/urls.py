from django.urls import path,include
from .views import *

urlpatterns = [
    path('internal_transfer/',HandleInternalTransaction.as_view(),name="internal_transfer" ),
    path('history/<int:account_number>/', HandleTransactionHistory.as_view(), name="transaction_history")
]
