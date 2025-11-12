from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1.0/',include('app.urls')),
    path('api/v1.0/analysis/', include('analytics.urls')),
    path('api/v1.0/auth/', include('auth_service.urls'))
]
