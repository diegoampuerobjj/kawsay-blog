from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Post, Category, Tag, Like, Comment
from .forms import PostForm, CategoryForm, TagForm, CommentForm

#RENDER THE BLOG HOME
class BlogHomeView(ListView):
    model = Post
    context_object_name = "posts"
    template_name = 'blog/blog_home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_posts"] = Post.objects.count()
        return context

#CREATE
class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post_form.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("post-detail", kwargs={"slug": self.object.slug})

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "blog/category_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "create-post")
        return context
    
    def get_success_url(self):
        return self.request.POST.get("next", "create-post")

class TagCreateView(LoginRequiredMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = "blog/tag_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "create-post")
        return context
    
    def get_success_url(self):
        return self.request.POST.get("next", "create-post")

#READ
class PostDetailView(FormMixin, DetailView):
    model = Post
    template_name = "blog/post_detail.html"
    form_class = CommentForm

    def get_success_url(self):
        return reverse("post-detail", kwargs={"slug": self.object.slug})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["comments"] = self.object.comments.filter(parent__isnull=True).order_by("-created_at")
        context["user_has_liked"] = (
            self.object.likes.filter(user=self.request.user).exists()
            if self.request.user.is_authenticated else False
        )
        context["likes_count"] = self.object.likes.count()
        return context
    
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)
    
    def form_valid(self, form):
        form.instance.post = self.object
        form.instance.user = self.request.user
        form.save()
        return super().form_valid(form)

#UPDATE
class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post_form.html"

    def get_success_url(self):
        return reverse("post-detail", kwargs={"slug": self.object.slug})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

#DELETE
class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name ="blog/post_confirm_delete.html"

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy("blog_home")


#LIKE
class ToggleLikeView(LoginRequiredMixin, View):
    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug)
        like, created = post.likes.get_or_create(user=request.user)

        if not created:
            like.delete()
        return redirect("post-detail", slug=post.slug)

#COMMENT
class CommentView(LoginRequiredMixin, View):
    def post(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        if request.user not in (comment.user, comment.post.author):
            return redirect("post-detail", slug=comment.post.slug)
        post_slug = comment.post.slug
        comment.delete()
        return redirect("post-detail", slug = post_slug)