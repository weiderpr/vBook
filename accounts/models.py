from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUser(AbstractUser):
    # The user asked for "name, email, password"
    # AbstractUser already has first_name and last_name, but we can add a single 'name' field
    # or just use first_name/last_name. Let's add a 'full_name' field for simplicity.
    full_name = models.CharField(max_length=255, verbose_name="Nome Completo")
    email = models.EmailField(unique=True, verbose_name="E-mail")
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, verbose_name="Foto de Perfil")
    theme_preference = models.CharField(
        max_length=10, 
        choices=[('light', 'Light'), ('dark', 'Dark')], 
        default='dark',
        verbose_name="Preferência de Tema"
    )
    language_preference = models.CharField(
        max_length=10,
        choices=[('pt-br', 'Português'), ('en', 'English')],
        default='pt-br',
        verbose_name="Preferência de Idioma"
    )
    mobile_theme_preference = models.CharField(
        max_length=10, 
        choices=[('light', 'Light'), ('dark', 'Dark')], 
        default='dark',
        verbose_name="Preferência de Tema Mobile"
    )

    # Evolution API / WhatsApp Fields
    whatsapp_instance_name = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name="Nome da Instância WhatsApp")
    whatsapp_instance_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Chave da Instância WhatsApp")
    whatsapp_connected = models.BooleanField(default=False, verbose_name="WhatsApp Conectado")

    # Admin field
    is_admin = models.BooleanField(default=False, verbose_name="Administrador")

    # Condominium association
    condo = models.ForeignKey(
        'administration.Condo', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='users',
        verbose_name="Condomínio"
    )

    USER_TYPE_CHOICES = [
        ('admin', 'Administrador do Sistema'),
        ('manager', 'Gestor de Propriedades'),
        ('staff', 'Colaborador de Condomínio'),
    ]
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='manager',
        verbose_name="Tipo de Usuário"
    )

    # Use email as the identifier for login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    @property
    def first_name_display(self):
        if self.full_name:
            return self.full_name.split()[0]
        return self.username.split('@')[0]

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email

