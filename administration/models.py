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
    is_automated = models.BooleanField(_("Portaria automatizada com VerticeBook?"), default=False)
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

class SystemSetting(models.Model):
    GATEWAY_CHOICES = [
        ('mercadopago', 'Mercado Pago'),
        ('stripe', 'Stripe'),
    ]
    
    pix_gateway = models.CharField(
        _("Gateway para PIX"),
        max_length=20,
        choices=GATEWAY_CHOICES,
        default='mercadopago'
    )
    
    card_gateway = models.CharField(
        _("Gateway para Cartão"),
        max_length=20,
        choices=GATEWAY_CHOICES,
        default='mercadopago'
    )
    
    # Mercado Pago Credentials
    mercadopago_public_key = models.CharField(_("Mercado Pago Public Key"), max_length=255, blank=True)
    mercadopago_access_token = models.CharField(_("Mercado Pago Access Token"), max_length=255, blank=True)
    mercadopago_webhook_secret = models.CharField(_("Mercado Pago Webhook Secret"), max_length=255, blank=True)
    
    # Stripe Credentials
    stripe_public_key = models.CharField(_("Stripe Public Key"), max_length=255, blank=True)
    stripe_secret_key = models.CharField(_("Stripe Secret Key"), max_length=255, blank=True)
    stripe_webhook_secret = models.CharField(_("Stripe Webhook Secret"), max_length=255, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Configuração do Sistema")
        verbose_name_plural = _("Configurações do Sistema")

    def __str__(self):
        return f"Configurações (PIX: {self.pix_gateway}, Cartão: {self.card_gateway})"
    
    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj
