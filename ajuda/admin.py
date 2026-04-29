from django.contrib import admin
from .models import ChatInteraction

@admin.register(ChatInteraction)
class ChatInteractionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'status', 'current_url')
    list_filter = ('status', 'created_at')
    search_fields = ('question', 'answer', 'user__email', 'user__full_name')
    readonly_fields = ('created_at',)
