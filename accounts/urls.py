from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('update-theme/', views.update_theme_preference, name='update_theme'),
    path('update-language/', views.update_language_preference, name='update_language'),
    path('whatsapp/', views.whatsapp_settings_view, name='whatsapp_settings'),
]
