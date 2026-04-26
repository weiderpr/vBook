from django.db import models
from django.conf import settings
from administration.models import Plan
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Subscription(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pendente')),
        ('active', _('Ativa')),
        ('expired', _('Expirada')),
        ('canceled', _('Cancelada')),
    ]
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='subscription',
        verbose_name=_("Usuário")
    )
    plan = models.ForeignKey(
        Plan, 
        on_delete=models.PROTECT, 
        related_name='subscriptions',
        verbose_name=_("Plano")
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        verbose_name=_("Status")
    )
    
    start_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Data de Início"))
    end_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Data de Expiração"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Assinatura")
        verbose_name_plural = _("Assinaturas")

    @property
    def is_valid(self):
        """Verifica se a assinatura está ativa e não expirada."""
        if self.status != 'active':
            return False
        if self.end_date and self.end_date < timezone.now():
            return False
        return True

    def __str__(self):
        return f"{self.user.email} - {self.plan.description} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Se a assinatura for ativada e não tiver data de início, definimos como agora
        if self.status == 'active' and not self.start_date:
            self.start_date = timezone.now()
        
        # Se tiver data de início e plano, mas não tiver data de expiração, calculamos
        if self.start_date and self.plan and not self.end_date:
            from datetime import timedelta
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
            
        super().save(*args, **kwargs)

class Payment(models.Model):
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE, 
        related_name='payments',
        verbose_name=_("Assinatura")
    )
    mp_payment_id = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name=_("ID Mercado Pago")
    )
    status = models.CharField(
        max_length=50,
        verbose_name=_("Status")
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        verbose_name=_("Valor")
    )
    payment_method = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        verbose_name=_("Método de Pagamento")
    )
    raw_data = models.JSONField(
        null=True, 
        blank=True,
        verbose_name=_("Dados Brutos")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Pagamento")
        verbose_name_plural = _("Pagamentos")
        ordering = ['-created_at']

    def __str__(self):
        return f"Pagamento {self.mp_payment_id} - {self.status}"
