from django.urls import path
from .views import help_center_view, chat_query_view

app_name = 'ajuda'

urlpatterns = [
    path('', help_center_view, name='help_center'),
    path('chat/', chat_query_view, name='chat_query'),
]
