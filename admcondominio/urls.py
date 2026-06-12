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
    path('unidades/<int:pk>/checkin-manual/', views.PropertyManualCheckinView.as_view(), name='property_manual_checkin'),
    path('checkin-manual/<int:pk>/detalhes/', views.ManualCheckinDetailsJsonView.as_view(), name='manual_checkin_details'),
    path('checkin-manual/<int:pk>/registrar-saida/', views.ManualCheckinExitView.as_view(), name='manual_checkin_exit'),
    path('checkin-manual/<int:pk>/desfazer-checkin/', views.ManualCheckinUndoView.as_view(), name='manual_checkin_undo'),
    path('historico/', views.HistoryListView.as_view(), name='history_list'),
    path('arquivos-portaria/', views.PortariaDriveView.as_view(), name='portaria_drive'),
    path('checkin/adicionar-visitantes/', views.AddVisitorsView.as_view(), name='add_visitors'),
    path('checkin/adicionar-acompanhantes/', views.AddCompanionsView.as_view(), name='add_companions'),
    path('checkin/remover-acompanhante/', views.DeleteCompanionView.as_view(), name='delete_companion'),
    path('checkin/remover-visitante/', views.DeleteVisitorView.as_view(), name='delete_visitor'),
    
    # Prestadores
    path('prestadores/', views.ProvidersListView.as_view(), name='provider_list'),
    path('prestadores/cadastrar/', views.ProviderCreateView.as_view(), name='provider_create'),
    path('prestadores/checkin/', views.ProviderCheckinView.as_view(), name='provider_checkin'),
    path('prestadores/checkout/<int:pk>/', views.ProviderCheckoutView.as_view(), name='provider_checkout'),
    path('prestadores/buscar/', views.ProviderSearchAPIView.as_view(), name='provider_search'),
    path('prestadores/acesso/<int:pk>/detalhes/', views.ProviderAccessDetailsJsonView.as_view(), name='provider_access_details'),
]
