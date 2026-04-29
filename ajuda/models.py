from django.db import models
from django.conf import settings

class ChatInteraction(models.Model):
    STATUS_CHOICES = [
        ('answered', 'Respondido'),
        ('unresolved', 'Incapacidade'),
        ('error', 'Erro do Sistema'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Usuário"
    )
    question = models.TextField(verbose_name="Pergunta")
    answer = models.TextField(verbose_name="Resposta", null=True, blank=True)
    current_url = models.CharField(max_length=255, verbose_name="Tela/URL")
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='answered',
        verbose_name="Status"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora")

    class Meta:
        verbose_name = "Interação do Chat"
        verbose_name_plural = "Interações do Chat"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.created_at.strftime('%d/%m/%Y %H:%M')}"
