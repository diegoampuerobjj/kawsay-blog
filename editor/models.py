from django.db import models
from blog.models import Post
from django.conf import settings

class PostVersion(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    content = models.TextField()
    excerpt = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['post', 'version_number']
        ordering = ['-version_number']

class PostAutosave(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='autosaves')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['post', 'user']
