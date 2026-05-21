from django.db import models
from blog.models import Post


class PostVersion(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    content = models.TextField()
    excerpt = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['post', 'version_number']
        ordering = ['-version_number']
