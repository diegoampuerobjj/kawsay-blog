# Class-Based Views Reference — `blog/views.py`

## Overview

This file contains all views for the `blog` Django app. Every view has been migrated from Function-Based Views (FBVs) to Class-Based Views (CBVs).

All authentication-restricted views use `LoginRequiredMixin` instead of the `@login_required` decorator.

---

## Table of Contents

1. [Imports Explained](#1-imports-explained)
2. [BlogHomeView (ListView)](#2-bloghomeview-listview)
3. [PostCreateView (CreateView)](#3-postcreateview-createview)
4. [CategoryCreateView & TagCreateView (CreateView + next)](#4-categorycreateview--tagcreateview-createview--next)
5. [PostDetailView (FormMixin + DetailView)](#5-postdetailview-formmixin--detailview)
6. [PostUpdateView (UpdateView)](#6-postupdateview-updateview)
7. [PostDeleteView (DeleteView)](#7-postdeleteview-deleteview)
8. [ToggleLikeView (View)](#8-togglelikeview-view)
9. [CommentView (View)](#9-commentview-view)
10. [CBV Patterns Summary](#10-cbv-patterns-summary)

---

## 1. Imports Explained

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Post, Category, Tag, Like, Comment
from .forms import PostForm, CategoryForm, TagForm, CommentForm
```

| Import | Purpose |
|--------|---------|
| `redirect`, `get_object_or_404` | Shortcuts for HTTP redirects and safe DB lookups |
| `reverse` | Resolves a URL name (e.g. `"post-detail"`) into a real URL at runtime |
| `reverse_lazy` | Same as `reverse` but evaluated lazily — used in class attributes (not methods) |
| `View` | The most basic CBV. Just routes HTTP methods (`get()`, `post()`, etc.) |
| `ListView` | Displays a list of model objects |
| `DetailView` | Displays a single model object |
| `CreateView` | Form view that creates a new model object |
| `UpdateView` | Form view that updates an existing model object |
| `DeleteView` | Confirmation view that deletes a model object |
| `FormMixin` | Adds form handling capabilities to any view |
| `LoginRequiredMixin` | Blocks unauthenticated users; redirects to login page |

### `reverse` vs `reverse_lazy`

```python
# GOOD in methods — evaluated at request time
def get_success_url(self):
    return reverse("post-detail", kwargs={"slug": self.object.slug})

# GOOD in class attributes — evaluated lazily
success_url = reverse_lazy("blog-home")

# BAD — would crash at import time
# success_url = reverse("blog-home")
```

---

## 2. BlogHomeView (ListView)

```python
class BlogHomeView(ListView):
    model = Post
    template_name = "blog/blog_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_posts"] = Post.objects.count()
        return context
```

### How it works

| Event | What happens |
|-------|-------------|
| `GET /` | `ListView.get()` fetches `Post.objects.all()` |
| `get_context_data()` | Adds `total_posts` to the template context |
| Template rendering | Context includes `post_list` (default) + `total_posts` |

### Key concepts

- **`model = Post`** tells Django which model to query.
- **`template_name`** is the HTML file to render.
- **`get_context_data()`** is the standard hook for adding extra template variables.
  - Always call `super().get_context_data()` first to get the base context.
  - Always `return context` at the end — forgetting this returns `None`.
- **`context_object_name`** (not set here) controls the template variable name. Default is `post_list`. To use `posts`, add `context_object_name = "posts"` as a class attribute.

---

## 3. PostCreateView (CreateView)

```python
class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post_form.html"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("post-detail", kwargs={"slug": self.object.slug})
```

### How it works

| Method | What happens |
|--------|-------------|
| `GET` | Renders `PostForm()` empty |
| `POST` (invalid) | Re-renders form with validation errors |
| `POST` (valid) | Calls `form_valid()`, saves, redirects to `get_success_url()` |

### `form_valid()` — The pre-save hook

Before saving, `form_valid()` lets you modify `form.instance` — the unsaved model object:

```python
def form_valid(self, form):
    form.instance.author = self.request.user  # assign author before save
    return super().form_valid(form)            # proceed with save + redirect
```

`super().form_valid(form)` internally:
1. Calls `form.save()` to persist the object.
2. Stores the object as `self.object`.
3. Calls `get_success_url()` and returns a redirect response.

### `get_success_url()` — Post-save redirect

Uses `reverse()` to convert the URL name `"post-detail"` + `slug` into a real URL like `/posts/my-post-slug/`.

---

## 4. CategoryCreateView & TagCreateView (CreateView + next)

```python
class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "blog/category_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "create-post")
        return context

    def get_success_url(self):
        return self.request.POST.get("next", "create-post")


class TagCreateView(LoginRequiredMixin, CreateView):
    # Identical pattern but uses TagForm and "tag_form.html"
    ...
```

### The `next` parameter pattern

This solves a common UX problem: a user is on the "create post" page and needs to create a new category or tag inline. The flow is:

```
Create Post page
  → Click "Add Category" → /categories/create/?next=create-post
  → Create the category
  → Redirect back to "create-post"
```

### `get_context_data()` — Reading `next` from the URL

```python
context["next"] = self.request.GET.get("next", "create-post")
```

The template uses this in a hidden input:

```html
<input type="hidden" name="next" value="{{ next }}">
```

### `get_success_url()` — Reading `next` from POST data

```python
return self.request.POST.get("next", "create-post")
```

When the form is submitted, the hidden `next` value comes back as POST data, and the view redirects there.

---

## 5. PostDetailView (FormMixin + DetailView)

```python
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
```

### Why `FormMixin` + `DetailView`?

`DetailView` only displays an object. But this page needs to **show a post AND accept a comment form** on the same URL. `FormMixin` adds form-handling capabilities.

### Why `FormMixin` comes first (MRO)

```python
class PostDetailView(FormMixin, DetailView):
```

**MRO (Method Resolution Order)**: `PostDetailView → FormMixin → DetailView`

Both `FormMixin` and `DetailView` define `get()`. By putting `FormMixin` first, its `get()` takes priority — which properly initializes the form and adds it to the template context.

If `DetailView` were first, its `get()` would run and the form would never be initialized automatically.

### GET flow

1. `FormMixin.get()` runs (inherited, not overridden).
2. `self.get_object()` comes from `DetailView` — fetches the Post by slug.
3. `self.get_form()` comes from `FormMixin` — creates an empty `CommentForm`.
4. `get_context_data()` runs — adds `comments`, `user_has_liked`, `likes_count`.
5. Template renders with `post`, `form`, `comments`, etc.

### POST flow

`DetailView` has no `post()` method, so we define one:

```python
def post(self, request, *args, **kwargs):
    if not request.user.is_authenticated:
        return redirect("login")
    self.object = self.get_object()
    form = self.get_form()
    if form.is_valid():
        return self.form_valid(form)
    else:
        return self.form_invalid(form)
```

Step by step:

1. **Authentication check** — redirect to login if not authenticated.
2. **`self.object = self.get_object()`** — fetch the Post; store it on `self` so `form_valid()` can use it.
3. **`form = self.get_form()`** — creates `CommentForm(request.POST)` bound to submitted data.
4. **Validation branch** — valid calls `form_valid()`, invalid calls `form_invalid()` (re-renders with errors).

### `form_valid()` — Saving the comment

```python
def form_valid(self, form):
    form.instance.post = self.object
    form.instance.user = self.request.user
    form.save()
    return super().form_valid(form)
```

The `CommentForm` likely only has `content` (and maybe `parent`) fields. The `post` and `user` must be set programmatically before saving. `super().form_valid(form)` calls `get_success_url()` and returns a redirect.

---

## 6. PostUpdateView (UpdateView)

```python
class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post_form.html"

    def get_success_url(self):
        return reverse("post-detail", kwargs={"slug": self.object.slug})
```

### How it works

| Method | What happens |
|--------|-------------|
| `GET` | Fetches existing Post by slug, pre-fills form with current data |
| `POST` (valid) | Saves changes to the **same** Post object, redirects |
| `POST` (invalid) | Re-renders form with errors |

`UpdateView` is structurally identical to `CreateView` — the key difference is that `UpdateView` works on an existing object (fetched by URL parameter) instead of creating a new one.

No `form_valid()` override is needed here because there is no additional field to assign (the author stays the same).

---

## 7. PostDeleteView (DeleteView)

```python
class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = "blog/post_confirm_delete.html"
    success_url = reverse_lazy("blog-home")
```

### How it works

| Method | What happens |
|--------|-------------|
| `GET` | Shows confirmation page with post details |
| `POST` | Deletes the post, redirects to `success_url` |

`DeleteView` is the simplest generic view. It has no form — just a confirmation template with a POST button.

### `reverse_lazy` for class attributes

`success_url = reverse_lazy("blog-home")` is a **class attribute**, evaluated when the module is imported. At import time, Django's URL patterns are not yet loaded, so `reverse()` would fail. `reverse_lazy()` defers the URL resolution until the first request.

---

## 8. ToggleLikeView (View)

```python
class ToggleLikeView(LoginRequiredMixin, View):
    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug)
        like, created = post.likes.get_or_create(user=request.user)

        if not created:
            like.delete()
        return redirect("post-detail", slug=post.slug)
```

### Why `View` and not `CreateView`/`UpdateView`?

This is a simple action with no form, no template, no model CRUD — just a POST handler that toggles a like. `View` is the minimal CBY that just routes HTTP methods.

### The toggle logic

```python
like, created = post.likes.get_or_create(user=request.user)
```

- `get_or_create()` returns `(object, boolean)`.
- `created=True` means a new Like was created (user **gave** a like).
- `created=False` means the Like already existed (user previously liked).

```python
if not created:
    like.delete()
```

- If it already existed → delete it (unlike).
- If it was just created → do nothing (already liked).

### URL parameter binding

The `slug` parameter in `def post(self, request, slug)` comes from the URL pattern:
```python
path("posts/<slug:slug>/like/", views.ToggleLikeView.as_view(), name="toggle-like")
```

---

## 9. CommentView (View)

```python
class CommentView(LoginRequiredMixin, View):
    def post(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        if request.user not in (comment.user, comment.post.author):
            return redirect("post-detail", slug=comment.post.slug)
        post_slug = comment.post.slug
        comment.delete()
        return redirect("post-detail", slug=post_slug)
```

### Authorization logic

Only two people can delete a comment:
- The comment's author (`comment.user`).
- The post's author (`comment.post.author`).

```python
if request.user not in (comment.user, comment.post.author):
    return redirect("post-detail", slug=comment.post.slug)
```

If neither, redirect without deleting.

### Why save `post_slug` before deleting?

```python
post_slug = comment.post.slug
comment.delete()
return redirect("post-detail", slug=post_slug)
```

After `comment.delete()`, the database row is gone. Trying to access `comment.post.slug` after deletion would raise an error because Django follows the foreign key via a database query. The slug is cached in the Python variable `post_slug`.

---

## 10. CBV Patterns Summary

### Pattern reference

| Pattern | Base Classes | Methods You Override | Use Case |
|---------|-------------|---------------------|----------|
| **Display list** | `ListView` | `get_context_data()` | Home page, search results |
| **Display detail** | `DetailView` | `get_context_data()` | Single post page |
| **Create object** | `CreateView` | `form_valid()`, `get_success_url()` | New post, category, tag |
| **Update object** | `UpdateView` | `get_success_url()` | Edit post |
| **Delete object** | `DeleteView` | (none, just attributes) | Delete post |
| **Detail + form** | `FormMixin`, `DetailView` | `post()`, `form_valid()`, `get_context_data()` | Post detail with comment form |
| **Simple action** | `View` | `post()` or `get()` | Like toggle, comment delete |

### Inheritance hierarchy

```
View
├── LoginRequiredMixin + ListView    → BlogHomeView
├── LoginRequiredMixin + CreateView  → PostCreateView, CategoryCreateView, TagCreateView
├── LoginRequiredMixin + UpdateView  → PostUpdateView
├── LoginRequiredMixin + DeleteView  → PostDeleteView
├── FormMixin + DetailView           → PostDetailView
└── LoginRequiredMixin + View        → ToggleLikeView, CommentView
```

### Template mapping

| View | Template |
|------|----------|
| `BlogHomeView` | `blog/blog_home.html` |
| `PostCreateView` | `blog/post_form.html` |
| `PostUpdateView` | `blog/post_form.html` |
| `CategoryCreateView` | `blog/category_form.html` |
| `TagCreateView` | `blog/tag_form.html` |
| `PostDetailView` | `blog/post_detail.html` |
| `PostDeleteView` | `blog/post_confirm_delete.html` |
| `ToggleLikeView` | No template (redirect only) |
| `CommentView` | No template (redirect only) |
