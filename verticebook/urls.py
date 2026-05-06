from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import landing_view, dashboard_view, service_worker

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', landing_view, name='landing'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('Ajuda/', include('ajuda.urls', namespace='ajuda')),
    path('accounts/', include('accounts.urls')),
    path('propriedades/', include('properties.urls')),
    path('propriedades/<int:property_pk>/reservas/', include('reservations.urls')),
    path('checkin/<uuid:token>/', include('reservations.urls_guest_checkin')),
    path('assinaturas/', include('subscriptions.urls')),
    path('administrador/', include('administration.urls', namespace='administration')),
    path('mobile/', include('mobile.urls')),
    path('mobilecondominio/', include('mobilecondominio.urls')),
    path('manutencoes/', include('maintenance.urls')),
    path('sw.js', service_worker, name='service_worker'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
