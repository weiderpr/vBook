from django.urls import path
from .views_checkin import GuestCheckInView

urlpatterns = [
    path('', GuestCheckInView.as_view(), name='guest_checkin_root'),
]
