from django.db import models
from django.utils.translation import gettext_lazy as _

class Condo(models.Model):
    name = models.CharField(_("Nome do Condomínio"), max_length=255)
    address_street = models.CharField(_("Rua"), max_length=255)
    address_number = models.CharField(_("Número"), max_length=50)
    address_neighborhood = models.CharField(_("Bairro"), max_length=100)
    address_city = models.CharField(_("Cidade"), max_length=100)
    address_state = models.CharField(_("Estado"), max_length=2)
    
    requires_authorization = models.BooleanField(_("Exige autorização de acesso"), default=False)
    authorization_template = models.TextField(_("Modelo de autorização"), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Condomínio")
        verbose_name_plural = _("Condomínios")
        ordering = ['name']

    def __str__(self):
        return self.name

class Plan(models.Model):
    PERIODICITY_CHOICES = [
        ('monthly', _('Mensal')),
        ('once', _('Única')),
    ]
    
    description = models.CharField(max_length=255, verbose_name=_("Descrição"))
    periodicity = models.CharField(max_length=20, choices=PERIODICITY_CHOICES, default='monthly', verbose_name=_("Periodicidade"))
    base_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=_("Valor base"))
    duration_days = models.PositiveIntegerField(verbose_name=_("Duração em dias"))
    is_active = models.BooleanField(default=True, verbose_name=_("Ativo"))
    requires_payment = models.BooleanField(default=True, verbose_name=_("Necessita Pagamento"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Plano")
        verbose_name_plural = _("Planos")
        ordering = ['-created_at']

    def __str__(self):
        return self.description
