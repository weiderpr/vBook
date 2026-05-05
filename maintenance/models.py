from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from properties.models import Property, ServiceProvider, Service

class Maintenance(models.Model):
    STATUS_CHOICES = [
        ('open', _('Aberta')),
        ('budgeting', _('Orçamento')),
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
    services = models.ManyToManyField(
        Service, 
        blank=True, 
        related_name='maintenances',
        verbose_name=_("Categorias de Serviço")
    )
    
    # Execution details
    provider_name = models.CharField(max_length=255, verbose_name=_("Prestador Final"), blank=True, null=True)
    provider_phone = models.CharField(max_length=20, verbose_name=_("Telefone Prestador"), blank=True, null=True)
    provider = models.ForeignKey(
        ServiceProvider, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='maintenances',
        verbose_name=_("Prestador Associado")
    )
    execution_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Valor Final"), blank=True, null=True)
    execution_start_date = models.DateField(verbose_name=_("Data Início Execução"), blank=True, null=True)
    execution_end_date = models.DateField(verbose_name=_("Data Fim Execução"), blank=True, null=True)

    is_archived = models.BooleanField(default=False, verbose_name=_("Arquivado"))
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

from django.core.files.base import ContentFile
import sys
from PIL import Image
from io import BytesIO

class MaintenancePhoto(models.Model):
    maintenance = models.ForeignKey(Maintenance, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='maintenance_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.image:
            # Open the image using PIL
            img = Image.open(self.image)
            
            # Check if it needs compression (2MB = 2 * 1024 * 1024 bytes)
            if self.image.size > 2 * 1024 * 1024:
                output = BytesIO()
                
                # If image is RGBA, convert to RGB for JPEG compression
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # Start with quality 85
                quality = 85
                img.save(output, format='JPEG', quality=quality, optimize=True)
                
                # If still over 2MB, reduce quality progressively
                while output.tell() > 2 * 1024 * 1024 and quality > 10:
                    output.seek(0)
                    output.truncate(0)
                    quality -= 10
                    img.save(output, format='JPEG', quality=quality, optimize=True)
                
                output.seek(0)
                # Create a new Django-friendly ContentFile
                self.image = ContentFile(output.read(), name=self.image.name)
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Foto da Manutenção")
        verbose_name_plural = _("Fotos da Manutenção")

class ProviderEvaluation(models.Model):
    maintenance = models.OneToOneField(
        Maintenance,
        on_delete=models.CASCADE,
        related_name='evaluation',
        verbose_name=_("Manutenção"),
        null=True,
        blank=True
    )
    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='evaluations',
        verbose_name=_("Prestador")
    )
    rating = models.IntegerField(verbose_name=_("Nota (1-5)"))
    comment = models.TextField(verbose_name=_("Comentário"), blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("Usuário")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Data da Avaliação"))

    class Meta:
        verbose_name = _("Avaliação do Prestador")
        verbose_name_plural = _("Avaliações dos Prestadores")

    def __str__(self):
        return f"{self.provider.name} - {self.rating} stars"
