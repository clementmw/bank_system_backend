# users,accounts,mpesatransaction,transaction,
from flask_admin.contrib.sqla import  ModelView

class UserAdminView(ModelView):
    column_sortable_list=('created_at','firstName','lastName')
    column_searchable_list = ('firstName','lastName','username','email','phone','role')
    column_list=('id','firstName','lastName','username','email','phone','address','isActive', 'role','created_at')
    column_labels=dict(name= 'Name',username='Username',email="Email",isActive = 'isActive', role ='Role')
    column_filters=column_list

class AccountAdminView(ModelView):
    column_sortable_list=('created_at', 'account_type', 'account_number')
    column_searchable_list = ('account_type', 'account_number')
    column_list=('id', 'account_type', 'account_number','user_id', 'created_at')
    column_labels=dict(name= 'Name', email="Email", isActive = 'isActive', role ='Role')
    column_filters=column_list

class TransactionAdminView(ModelView):
    column_sortable_list=('created_at','transaction_type','user_id','receiver_id','account_id')
    column_searchable_list = ('transaction_type','description','amount','user_id','receiver_id','account_id')
    column_list=('id','transaction_type','description','amount','user_id','receiver_id','account_id')
    column_labels=dict(transaction_type='Transaction_Type',amount='Amount')
    column_filters=column_list




