from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    path('<int:pk>/', views.MaintenanceDashboardView.as_view(), name='dashboard'),
    path('list/<int:property_pk>/', views.MaintenanceListView.as_view(), name='list_ajax'),
    path('detail/<int:pk>/', views.MaintenanceDetailView.as_view(), name='detail_ajax'),
    path('create/<int:property_pk>/', views.MaintenanceCreateView.as_view(), name='create'),
    path('update-status/<int:pk>/', views.MaintenanceUpdateStatusView.as_view(), name='update_status'),
    path('add-budget/<int:maintenance_pk>/', views.MaintenanceBudgetCreateView.as_view(), name='add_budget'),
    path('delete-budget/<int:pk>/', views.MaintenanceBudgetDeleteView.as_view(), name='delete_budget'),
    path('budget-detail/<int:pk>/', views.MaintenanceBudgetDetailView.as_view(), name='budget_detail'),
    path('upload-photo/<int:maintenance_pk>/', views.MaintenancePhotoUploadView.as_view(), name='upload_photo'),
    path('delete-photo/<int:pk>/', views.MaintenancePhotoDeleteView.as_view(), name='delete_photo'),
]
