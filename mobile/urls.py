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
    path('propriedade/<int:property_pk>/reserva/<int:pk>/enviar-autorizacao/', views.mobile_send_authorization_whatsapp, name='send_authorization_whatsapp'),
    path('reserva/<int:pk>/cancelar/', views.mobile_reservation_cancel, name='reservation_cancel'),
    path('reserva/<int:pk>/excluir/', views.mobile_reservation_delete, name='reservation_delete'),
    path('reserva/<int:pk>/reativar/', views.mobile_reservation_reactivate, name='reservation_reactivate'),
    path('reserva/<int:pk>/custo/novo/', views.mobile_add_reservation_cost, name='reservation_cost_add'),
    path('reserva/<int:pk>/pagamento/novo/', views.mobile_add_reservation_payment, name='reservation_payment_add'),
    path('reserva/<int:pk>/custo/<int:cost_id>/excluir/', views.mobile_delete_reservation_cost, name='reservation_cost_delete'),
    path('reserva/<int:pk>/pagamento/<int:payment_id>/excluir/', views.mobile_delete_reservation_payment, name='reservation_payment_delete'),
    path('perfil/', views.mobile_profile, name='profile'),
    path('perfil/senha/', views.mobile_password_change, name='password_change'),
    path('perfil/update-theme/', views.mobile_update_theme, name='update_theme'),
    path('planos/', views.mobile_plans, name='plans'),
    path('financeiro/', views.mobile_financeiro, name='financeiro'),
    path('operacional/', views.mobile_operacional, name='operacional'),
    path('notifications/', views.mobile_notifications, name='notifications'),
    path('notifications/<int:pk>/read/', views.mobile_mark_notification_read, name='notification_read'),
    path('notifications/read-all/', views.mobile_mark_all_notifications_read, name='notifications_read_all'),
    path('subscribe-push/', views.mobile_subscribe_push, name='subscribe_push'),
]
