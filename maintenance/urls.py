from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    # New Standard CRUD & Wizard
    path('<int:property_pk>/', views.MaintenanceListView.as_view(), name='list'),
    path('<int:property_pk>/nova/', views.MaintenanceCreateView.as_view(), name='create'),
    path('<int:property_pk>/<int:pk>/wizard/', views.MaintenanceWizardView.as_view(), name='wizard'),
    path('<int:property_pk>/<int:pk>/editar/', views.MaintenanceUpdateView.as_view(), name='update'),
    path('<int:property_pk>/<int:pk>/excluir/', views.MaintenanceDeleteView.as_view(), name='delete'),

    # Legacy AJAX / Dashboard Views (Kept for compatibility)
    path('<int:pk>/dashboard/', views.MaintenanceDashboardView.as_view(), name='dashboard'),
    path('list-ajax/<int:property_pk>/', views.MaintenanceListViewOld.as_view(), name='list_ajax'),
    path('detail-ajax/<int:pk>/', views.MaintenanceDetailView.as_view(), name='detail_ajax'),
    path('create-ajax/<int:property_pk>/', views.MaintenanceCreateViewOld.as_view(), name='create_ajax'),
    path('update-status/<int:pk>/', views.MaintenanceUpdateStatusView.as_view(), name='update_status'),
    path('add-budget/<int:maintenance_pk>/', views.MaintenanceBudgetCreateView.as_view(), name='add_budget'),
    path('delete-budget/<int:pk>/', views.MaintenanceBudgetDeleteView.as_view(), name='delete_budget'),
    path('budget-detail/<int:pk>/', views.MaintenanceBudgetDetailView.as_view(), name='budget_detail'),
    path('upload-photo/<int:maintenance_pk>/', views.MaintenancePhotoUploadView.as_view(), name='upload_photo'),
    path('delete-photo/<int:pk>/', views.MaintenancePhotoDeleteView.as_view(), name='delete_photo'),
    path('provider-autocomplete/', views.ProviderAutocompleteView.as_view(), name='provider_autocomplete'),
]
