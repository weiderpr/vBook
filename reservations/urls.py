from django.urls import path
from . import views, views_checkin
from .views_checkin import GuestCheckInView

app_name = 'reservations'

urlpatterns = [
    path('', views.ReservationListView.as_view(), name='list'),
    path('nova/', views.ReservationCreateView.as_view(), name='create'),
    path('buscar-clientes/', views.search_clients, name='search_clients'),
    path('<int:pk>/editar/', views.ReservationUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.ReservationDeleteView.as_view(), name='delete'),
    path('<int:pk>/whatsapp/', views.send_whatsapp_reservation, name='send_whatsapp'),
    path('<int:pk>/dados-hospede/', views_checkin.ReservationGuestDetailView.as_view(), name='guest_detail'),
    path('<int:pk>/autorizacao/', views_checkin.ReservationAuthorizationPDFView.as_view(), name='authorization_pdf'),
    path('<int:pk>/enviar-whatsapp/', views_checkin.ReservationSendAuthorizationWhatsAppView.as_view(), name='reservation_send_whatsapp'),
    path('<int:pk>/reset-checkin/', views_checkin.ReservationCheckInResetView.as_view(), name='reset_checkin'),
    path('checkin/<uuid:token>/', GuestCheckInView.as_view(), name='guest_checkin'),
    path('checkin/<uuid:token>/autorizacao/', views_checkin.GuestAuthorizationPDFView.as_view(), name='guest_authorization_pdf'),
    path('checkin/<uuid:token>/instrucoes/', views_checkin.GuestPropertyInstructionsView.as_view(), name='guest_instructions'),
]
