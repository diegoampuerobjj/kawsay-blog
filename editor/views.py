import mistune
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from blog.models import Post
from blog.forms import PostForm
from .models import PostVersion


# URL:    editor/posts/create/
# Método: GET → editor.html vacío
#         POST → valida, crea Post + PostVersion v1, redirect a post-detail
class EditorCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'editor/editor.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        self.object = form.save()
        PostVersion.objects.create(
            post=self.object,
            version_number=1,
            content=self.object.content,
            excerpt=self.object.excerpt,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('post-detail', kwargs={'slug': self.object.slug})


# URL:    editor/posts/<slug>/edit/
# Método: GET → carga Post, editor.html
#         POST → guarda Post + crea nueva PostVersion
class EditorUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'editor/editor.html'

    def form_valid(self, form):
        self.object = form.save()
        latest = self.object.versions.first()
        new_vn = (latest.version_number + 1) if latest else 1
        PostVersion.objects.create(
            post=self.object,
            version_number=new_vn,
            content=self.object.content,
            excerpt=self.object.excerpt,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('post-detail', kwargs={'slug': self.object.slug})


# URL:    editor/posts/<slug>/publish/
# Método: POST → setea published_at, redirect a post-detail
class PublishView(LoginRequiredMixin, View):
    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        if not post.content.strip():
            messages.error(request, "Can't publish an empty post.")
            return redirect('editor:edit', slug=post.slug)
        if not post.published_at:
            post.published_at = timezone.now().date()
            post.save(update_fields=['published_at'])
        return redirect('post-detail', slug=post.slug)


# URL:    editor/posts/<slug>/versions/
# Método: GET → lista de PostVersion ordenada descendente
class VersionHistoryView(LoginRequiredMixin, View):
    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        versions = post.versions.all()
        return render(request, 'editor/version_history.html', {
            'post': post,
            'versions': versions,
        })


# URL:    editor/posts/<slug>/versions/<int:version_number>/restore/
# Método: POST → crea NUEVA versión con el contenido restaurado, redirect a edit
class RestoreVersionView(LoginRequiredMixin, View):
    def post(self, request, slug, version_number):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        version = get_object_or_404(PostVersion, post=post, version_number=version_number)
        latest = post.versions.first()
        new_vn = (latest.version_number + 1) if latest else 1
        PostVersion.objects.create(
            post=post,
            version_number=new_vn,
            content=version.content,
            excerpt=version.excerpt,
        )
        post.content = version.content
        post.excerpt = version.excerpt
        post.save(update_fields=['content', 'excerpt'])
        return redirect('editor:edit', slug=post.slug)


# URL:    editor/posts/<slug>/preview/
# Método: GET → renderiza Markdown a HTML, muestra template de preview
class PreviewView(LoginRequiredMixin, View):
    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug, author=request.user)
        html = mistune.html(post.content)
        return render(request, 'editor/preview.html', {
            'post': post,
            'html': html,
        })
