from django.urls import path
from . import views

app_name = 'ajuda'

urlpatterns = [
    path('', views.help_center_view, name='help_center'),
    path('chat/query/', views.chat_query_view, name='chat_query'),
    path('chat/wizard/', views.chat_wizard_step_view, name='chat_wizard_step'),
    path('save-preference/', views.save_help_preference, name='save_preference'),
]
