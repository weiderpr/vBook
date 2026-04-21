from django.urls import path
from . import views

app_name = 'reservations_guest'

urlpatterns = [
    path('', views.CompleteGuestDataView.as_view(), name='complete_guest_data'),
]
