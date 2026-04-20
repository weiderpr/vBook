from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    path('', views.ReservationListView.as_view(), name='list'),
    path('nova/', views.ReservationCreateView.as_view(), name='create'),
    path('buscar-clientes/', views.search_clients, name='search_clients'),
    path('<int:pk>/editar/', views.ReservationUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.ReservationDeleteView.as_view(), name='delete'),
]
