from django.db import models
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        verbose_name="Usuário"
    )
    title = models.CharField(max_length=255, verbose_name="Título")
    message = models.TextField(verbose_name="Mensagem")
    link = models.CharField(max_length=255, blank=True, null=True, verbose_name="Link")
    is_read = models.BooleanField(default=False, verbose_name="Lida")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.email}"

class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='push_subscriptions',
        verbose_name="Usuário"
    )
    endpoint = models.TextField(verbose_name="Endpoint")
    p256dh = models.CharField(max_length=255, verbose_name="P256dh Key")
    auth = models.CharField(max_length=255, verbose_name="Auth Key")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")

    class Meta:
        verbose_name = "Assinatura Push"
        verbose_name_plural = "Assinaturas Push"

    def __str__(self):
        return f"Subscription for {self.user.email}"
