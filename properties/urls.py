from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.PropertyListView.as_view(), name='list'),
    path('nova/', views.PropertyCreateView.as_view(), name='create'),
    path('<int:pk>/painel/', views.PropertyDashboardView.as_view(), name='dashboard'),
    path('<int:pk>/editar/', views.PropertyUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.PropertyDeleteView.as_view(), name='delete'),
    path('<int:pk>/configuracoes/', views.PropertySettingsView.as_view(), name='settings'),
    path('<int:pk>/instrucoes/', views.PropertyInstructionsUpdateView.as_view(), name='instructions'),
    path('<int:pk>/autorizacao/', views.PropertyAuthorizationUpdateView.as_view(), name='authorization'),
    path('<int:pk>/configuracoes/custos/novo/', views.PropertyCostCreateView.as_view(), name='cost_create'),
    path('configuracoes/custos/<int:pk>/editar/', views.PropertyCostUpdateView.as_view(), name='cost_update'),
    path('configuracoes/custos/<int:pk>/excluir/', views.PropertyCostDeleteView.as_view(), name='cost_delete'),
    path('configuracoes/historico/salvar/<int:pk>/', views.PropertyFinancialHistorySaveView.as_view(), name='history_save'),
    
    # Prestadores de Serviço (Globais)
    path('prestadores/', views.ServiceProviderListView.as_view(), name='provider_list'),
    path('prestadores/novo/', views.ServiceProviderCreateView.as_view(), name='provider_create'),
    path('prestadores/buscar/', views.ServiceProviderSearchView.as_view(), name='provider_search'),
    path('prestadores/<int:pk>/editar/', views.ServiceProviderUpdateView.as_view(), name='provider_update'),
    path('prestadores/<int:pk>/excluir/', views.ServiceProviderDeleteView.as_view(), name='provider_delete'),
    path('servicos/novo/', views.ServiceCreateView.as_view(), name='service_create'),
    path("servicos/<int:pk>/editar/", views.ServiceUpdateView.as_view(), name="service_update"),
    path("servicos/<int:pk>/excluir/", views.ServiceDeleteView.as_view(), name="service_delete"),
    path('acesso-prestador/<uuid:token>/', views.ServiceProviderPublicView.as_view(), name='provider_public'),
    path('acesso-prestador/<uuid:token>/concluir/<int:cost_id>/', views.ServiceProviderCompleteServiceView.as_view(), name='provider_complete_service'),
    path('acesso-prestador/<uuid:token>/cancelar-conclusao/<int:cost_id>/', views.ServiceProviderCancelCompletionView.as_view(), name='provider_cancel_completion'),
]
