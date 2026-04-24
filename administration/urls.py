from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    path('', views.AdminDashboardView.as_view(), name='dashboard'),
    
    # Usuários
    path('usuarios/', views.UserListView.as_view(), name='user_list'),
    path('usuarios/novo/', views.UserCreateView.as_view(), name='user_create'),
    path('usuarios/<int:pk>/editar/', views.UserUpdateView.as_view(), name='user_edit'),
    path('usuarios/<int:pk>/excluir/', views.UserDeleteView.as_view(), name='user_delete'),

    # Categorias de Serviço
    path('categorias-servico/', views.ServiceCategoryListView.as_view(), name='service_category_list'),
    path('categorias-servico/novo/', views.ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('categorias-servico/<int:pk>/editar/', views.ServiceCategoryUpdateView.as_view(), name='service_category_edit'),
    path('categorias-servico/<int:pk>/excluir/', views.ServiceCategoryDeleteView.as_view(), name='service_category_delete'),

    # Condomínios
    path('condominios/', views.CondoListView.as_view(), name='condo_list'),
    path('condominios/novo/', views.CondoCreateView.as_view(), name='condo_create'),
    path('condominios/<int:pk>/editar/', views.CondoUpdateView.as_view(), name='condo_edit'),
    path('condominios/<int:pk>/excluir/', views.CondoDeleteView.as_view(), name='condo_delete'),
]
