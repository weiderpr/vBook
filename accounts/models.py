from django.contrib.auth.models import AbstractUser
from django.db import models

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

    # Use email as the identifier for login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
