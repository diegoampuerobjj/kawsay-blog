from django.db import models
from django.utils.text import slugify
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    slug = models.SlugField(max_length=100, blank=True)
    description = models.CharField(max_length=300)
    created_at = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'slug'], name='unique_user_category_slug'),
            models.UniqueConstraint(fields=['user', 'name'], name='unique_user_category_name'),
        ]
    
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # The save override is here to auto-fill slug fields so you do not have to type them every time.
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name= "posts")
    title = models.CharField(max_length=100)
    featured_image = models.ImageField(upload_to="posts/featured/", blank=True, null=True)
    tags = models.ManyToManyField("Tag", related_name="posts", blank=True)
    slug = models.SlugField(unique=True, max_length=100, blank=True)
    excerpt = models.CharField(max_length=300)
    content = models.TextField()
    published_at = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name_plural = "Posts"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Auto-generate slug from name/title if it is empty, so editors do not need to fill it manually.
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def number_of_comments(self):
        return Comment.objects.filter(post=self).count()

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Comments"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["post", "-created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id.username}: {self.content[:40]}"

class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Prevent duplicate likes per post: one user can like a given post only once (enforced at DB level)."""
        constraints = [
            models.UniqueConstraint(fields=["post", "user"], name="unique_post_user_like")
        ]

class Tag(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=100, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-generate slug from name/title if it is empty, so editors do not need to fill it manually.
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)