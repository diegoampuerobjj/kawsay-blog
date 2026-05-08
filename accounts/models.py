from django.db import models
from django.urls import reverse
from django.conf import settings


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100) 
    website = models.CharField(max_length=200) 
    bio = models.TextField(blank=True)

    class Meta:
        verbose_name = "Profile" 
        verbose_name_plural = "Profiles" 
    def __str__(self):
        return self.display_name or self.user.username