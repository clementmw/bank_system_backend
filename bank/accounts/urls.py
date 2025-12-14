from .views import *
from django.urls import path



urlpatterns = [
    path('create/account/', AccountView.as_view(), name='accounts'),
    path('details/', ManageAccounts.as_view(), name='account-detail'),
    path('approve/<str:account_id>/', ApproveAccounts.as_view(), name='account-approve'),
    path('reject/<str:account_id>/', RejectAccounts.as_view(), name='account-reject'),
    path('freeze/<str:account_id>/', FreezeAccounts.as_view(), name='account-freeze'),
    path('unfreeze/<str:account_id>/', HandleUnfreezingAccounts.as_view(), name='account-unfreeze'),
    path('close/request/<str:account_id>/', HandleRequestCloseAccount.as_view(), name='account-unfreeze'),
    path('close/process/<str:account_id>/', handleCloseRequest.as_view(), name='account-delete'),
    path('limit/<str:account_id>/', AccountLimitView.as_view(), name='account-update limits'),



]