from django.urls import path
from . import views_checkin

urlpatterns = [
    path('', views_checkin.GuestCheckInView.as_view(), name='guest_checkin'),
    path('autorizacao/', views_checkin.GuestAuthorizationPDFView.as_view(), name='guest_authorization_pdf'),
    path('instrucoes/', views_checkin.GuestPropertyInstructionsView.as_view(), name='guest_instructions'),
]
