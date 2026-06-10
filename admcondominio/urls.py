from django.urls import path
from . import views

app_name = 'admcondominio'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('unidades/', views.PropertiesListView.as_view(), name='properties_list'),
    path('unidades/cadastrar/', views.PropertyManualCreateView.as_view(), name='property_manual_create'),
    path('unidades/<int:pk>/customizar/', views.PropertyCustomizationView.as_view(), name='property_customize'),
    path('reserva/<int:pk>/liberar-entrada/', views.GateReleaseEntryView.as_view(), name='gate_release_entry'),
    path('reserva/<int:pk>/desfazer-entrada/', views.GateReleaseUndoView.as_view(), name='gate_release_undo'),
    path('reserva/<int:pk>/registrar-saida/', views.GateReleaseExitView.as_view(), name='gate_release_exit'),
    path('reserva/<int:pk>/detalhes/', views.ReservationDetailsJsonView.as_view(), name='reservation_details'),
]
