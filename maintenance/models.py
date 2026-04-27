from django.db import models
from django.utils.translation import gettext_lazy as _
from properties.models import Property

class Maintenance(models.Model):
    STATUS_CHOICES = [
        ('open', _('Aberta')),
        ('in_progress', _('Em andamento')),
        ('finished', _('Finalizada')),
        ('cancelled', _('Cancelada')),
    ]

    property = models.ForeignKey(
        Property, 
        on_delete=models.CASCADE, 
        related_name='maintenances',
        verbose_name=_("Propriedade")
    )
    title = models.CharField(max_length=255, verbose_name=_("Título"))
    description = models.TextField(verbose_name=_("Descrição"), blank=True, null=True)
    start_date = models.DateField(verbose_name=_("Data de Início"))
    end_date = models.DateField(verbose_name=_("Data de Fim"))
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='open',
        verbose_name=_("Status")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Manutenção")
        verbose_name_plural = _("Manutenções")
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.title} - {self.property.name}"

class Budget(models.Model):
    maintenance = models.ForeignKey(Maintenance, on_delete=models.CASCADE, related_name='budgets')
    provider_name = models.CharField(max_length=255, verbose_name=_("Nome Completo"))
    phone = models.CharField(max_length=20, verbose_name=_("Telefone"))
    value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Valor do Orçamento"))
    start_date = models.DateField(verbose_name=_("Previsão Início"))
    end_date = models.DateField(verbose_name=_("Previsão Fim"))
    observations = models.TextField(blank=True, null=True, verbose_name=_("Observações"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Orçamento")
        verbose_name_plural = _("Orçamentos")
        ordering = ['value']

    def __str__(self):
        return f"{self.provider_name} - {self.value}"

class MaintenancePhoto(models.Model):
    maintenance = models.ForeignKey(Maintenance, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='maintenance_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Foto da Manutenção")
        verbose_name_plural = _("Fotos da Manutenção")
