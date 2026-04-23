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
]
