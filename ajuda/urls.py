from django.urls import path
from .views import help_center_view

app_name = 'ajuda'

urlpatterns = [
    path('', help_center_view, name='help_center'),
]
