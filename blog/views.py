from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Post, Like, Comment
from .forms import PostForm, CategoryForm, TagForm, CommentForm

#RENDER THE BLOG HOME
def blog_home(request):
    posts = Post.objects.all()
    total_posts = Post.objects.count()
    return render(request, 'blog/blog-home.html', {"posts": posts, "total_posts": total_posts})

#CREATE
@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False) #don't save to the db yet
            post.author = request.user #setting the autor
            post.save() #now i can save
            form.save_m2m()
            return redirect('post-detail', slug=post.slug)
    else: # GET request - show empty form
        form = PostForm()
    return render(request, 'blog/post_form.html', {'form': form})

@login_required
def create_category(request):
    next_url = request.GET.get('next') or request.POST.get('next') or 'create-post'
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(next_url)
        else:
            form = CategoryForm(request.POST)
    else:
        form = CategoryForm()
    return render(request, 'blog/category_form.html', {'form': form, 'next': next_url})


@login_required
def create_tag(request):
    next_url = request.GET.get('next') or request.POST.get('next') or 'create-post'
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(next_url)
        else:
            form = TagForm(request.POST)
    else:
        form = TagForm()
    return render(request, 'blog/tag_form.html', {'form': form, 'next': next_url})

#READ
def read_post(request, slug):
    post = get_object_or_404(Post, slug=slug)
    comments = post.comments.filter(parent__isnull=True).order_by('-created_at')
    user_has_liked = False
    if request.user.is_authenticated:
        user_has_liked = post.likes.filter(user=request.user).exists()
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.user = request.user
            comment.save()
            return redirect('post-detail', slug=post.slug)
    else:
        form = CommentForm()
    
    context = {
        'post': post,
        'comments': comments,
        'user_has_liked': user_has_liked,
        'likes_count': post.likes.count(),
        'form': form
    }
    return render(request, 'blog/post_detail.html', context)

#UPDATE
@login_required
def update_post(request, slug):
    post = get_object_or_404(Post, slug=slug)
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save_m2m()
            return redirect('post-detail', slug=post.slug)
    else:
        form = PostForm(instance=post)
    return render(request, 'blog/post_form.html', {'form': form})

#DELETE
@login_required
def delete_post(request, slug):
    post = get_object_or_404(Post, slug=slug)
    if request.method == 'POST':
        post.delete()
        return redirect('blog-home')
    return render(request, 'blog/post_confirm_delete.html', {'post', post})

#LIKE
@login_required
def toggle_like(request, slug):
    post = get_object_or_404(Post, slug=slug)
    like, created = post.likes.get_or_create(user=request.user)
    if not created:
        like.delete()
    return redirect('post-detail', slug=post.slug)

#COMMENT
@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    post_slug = comment.post.slug
    if request.user == comment.user or request.user == comment.post.author:
        comment.delete()
    return redirect('post-detail', slug=post_slug)