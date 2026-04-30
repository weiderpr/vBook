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
    path('usuarios/<int:pk>/plano/', views.UserPlanDetailAjaxView.as_view(), name='user_plan_json'),
    path('usuarios/<int:pk>/remover-plano/', views.UserPlanRemoveView.as_view(), name='user_plan_remove'),
    path('usuarios/<int:pk>/alterar-vencimento/', views.UserPlanUpdateDateView.as_view(), name='user_plan_update_date'),

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
    path('condominios/<int:pk>/json/', views.CondoDetailAjaxView.as_view(), name='condo_detail_json'),
    
    # Usuários do Condomínio (Gerenciamento interno)
    path('condominios/<int:pk>/usuarios/', views.CondoUserListView.as_view(), name='condo_user_list'),
    path('condominios/<int:pk>/usuarios/novo/', views.CondoUserCreateView.as_view(), name='condo_user_create'),
    path('condominios/usuarios/<int:pk>/editar/', views.CondoUserUpdateView.as_view(), name='condo_user_edit'),
    path('condominios/usuarios/<int:pk>/excluir/', views.CondoUserDeleteView.as_view(), name='condo_user_delete'),
    
    # Planos
    path('planos/', views.PlanListView.as_view(), name='plan_list'),
    path('planos/novo/', views.PlanCreateView.as_view(), name='plan_create'),
    path('planos/<int:pk>/editar/', views.PlanUpdateView.as_view(), name='plan_edit'),
    path('planos/<int:pk>/excluir/', views.PlanDeleteView.as_view(), name='plan_delete'),

    # Configurações Globais
    path('configuracoes/', views.SystemSettingUpdateView.as_view(), name='settings'),

    # Interações do Chat
    path('interacoes-chat/', views.ChatInteractionListView.as_view(), name='chat_interaction_list'),
    path('interacoes-chat/<int:pk>/', views.ChatInteractionDetailView.as_view(), name='chat_interaction_detail'),
]
