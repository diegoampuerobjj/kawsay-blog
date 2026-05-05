from django.db import models
from django.urls import reverse


class User(models.Model):
    """Only one admin or superuser will exist, but there will be multiple users that can see and comment on the blog posts"""
    username = models.CharField(max_length=100)
    email = models.EmailField()
    password = models.CharField(max_length=50)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]

    def __str__(self):
        return self.username

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100) 
    website = models.CharField(max_length=200) 
    bio = models.TextField(blank=True)

    class Meta:
        verbose_name = "Profile" 
        verbose_name_plural = "Profiles" 
    def __str__(self):
        return self.display_name or self.user.username