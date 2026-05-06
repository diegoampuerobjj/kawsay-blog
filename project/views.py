from django.shortcuts import render

from blog.models import Post

def home(request):
    """Render the homepage."""
    posts = Post.objects.all()
    total_posts = Post.objects.count()
    return render(request, 'home.html', {"posts": posts, "total_posts": total_posts})