from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100, blank=True) 
    website = models.CharField(max_length=200, blank=True) 
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='accounts/avatars/', blank=True)

    class Meta:
        verbose_name = "Profile" 
        verbose_name_plural = "Profiles" 
    def __str__(self):
        return self.display_name or self.user.username
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)