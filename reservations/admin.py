from django.contrib import admin, messages
from .models import Reservation, ReservationCost
from .services.evolution_api import EvolutionService

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'property', 'start_date', 'end_date', 'total_value', 'created_at')
    list_filter = ('property', 'start_date')
    search_fields = ('client_name', 'property__name')
    actions = ['enviar_whatsapp_checkin']

    @admin.action(description="Enviar Link de Check-in via WhatsApp")
    def enviar_whatsapp_checkin(self, request, queryset):
        service = EvolutionService()
        success_count = 0
        error_count = 0
        
        for reservation in queryset:
            success, msg = service.enviar_link_checkin(reservation.id)
            if success:
                success_count += 1
            else:
                error_count += 1
                self.message_user(request, f"Erro na reserva {reservation.client_name}: {msg}", messages.ERROR)
        
        if success_count:
            self.message_user(request, f"{success_count} mensagens enviadas com sucesso.", messages.SUCCESS)
        if error_count:
            self.message_user(request, f"{error_count} mensagens falharam.", messages.WARNING)

@admin.register(ReservationCost)
class ReservationCostAdmin(admin.ModelAdmin):
    list_display = ('description', 'reservation', 'value')
    list_filter = ('reservation',)
