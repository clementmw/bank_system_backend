from django.contrib import admin
from django.urls import path,include
from rest_framework import permissions
from django_prometheus import exports
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView



urlpatterns = [
   path('admin/', admin.site.urls),
   path('api/v1.0/accounts/',include('accounts.urls')),
   path('api/v1.0/analysis/', include('analytics.urls')),
   path('api/v1.0/auth/', include('auth_service.urls')),
   path('api/v1.0/transactions/', include('transactions.urls')),
   path('api/v1.0/fraud/', include('fraud_service.urls')),


   
   
   #documentation
   path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
   path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
   path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),    #metrics prometheus
   #metrics
   path('', include('django_prometheus.urls')),
   path('metrics/', exports.ExportToDjangoView, name='metrics'),
]
