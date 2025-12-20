from .views import *
from django.urls import path
from .services.mpesaintegration import *



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
    path('limit/override/request/<str:account_id>/', HandleRequestOverride.as_view(), name='limit-override-request'),
    path('holds/<str:account_id>/', HandleAccountHold.as_view(), name='account-holds'),
    path('mpesa-b2c/', businessTocustomer, name='mpesa-callback'),
    path('mpesa-stk-push/', initiate_stk_push, name='mpesa-stk-push'),
    path('stk-callback/', safaricom_stk_callback, name='safaricom-callback'),
    path('b2c-callback/', safaricom_b2c_callback, name='safaricom-callback'),




]