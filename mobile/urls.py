from django.urls import path
from . import views

app_name = 'mobile'

urlpatterns = [
    path('home/', views.mobile_home, name='home'),
    path('reservas-hoje/', views.mobile_reservations_today, name='reservations_today'),
    path('propriedade/<int:pk>/', views.mobile_property_detail, name='property_detail'),
    path('propriedade/<int:property_pk>/reserva/nova/', views.mobile_reservation_create, name='reservation_create'),
    path('reserva/<int:pk>/editar/', views.mobile_reservation_edit, name='reservation_edit'),
    path('reserva/<int:pk>/', views.mobile_reservation_detail, name='reservation_detail'),
    path('propriedade/<int:property_pk>/reserva/<int:pk>/whatsapp/', views.mobile_send_whatsapp_reservation, name='send_whatsapp_reservation'),
]
