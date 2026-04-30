from django.urls import path
from . import views

app_name = 'mobilecondominio'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('scan/', views.QRScannerView.as_view(), name='scan'),
    path('reserva/<int:pk>/', views.ReservationDetailView.as_view(), name='reservation_detail'),
    path('reserva/<int:pk>/liberar/', views.GateReleaseView.as_view(), name='gate_release'),
    path('reserva/<int:pk>/checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('hospedes/', views.ActiveGuestsListView.as_view(), name='active_guests'),
    path('process-token/<uuid:token>/', views.QRCheckInDetailView.as_view(), name='process_token'),
    path('perfil/', views.ProfileView.as_view(), name='profile'),
    path('perfil/senha/', views.ChangePasswordView.as_view(), name='change_password'),
    path('perfil/tema/', views.UpdateThemeView.as_view(), name='update_theme'),
    path('diario/', views.DailyReservationsListView.as_view(), name='daily_reservations'),
]
