from django.urls import path
from . import views

"""
¿Qué hace as_view()?
1. Crea una función (closure) que Django puede llamar como cualquier view function.
2. Cuando llega un request, esa función:
   - Instancia la clase (view = BlogHomeView()).
   - Configura atributos como args, kwargs, request en la instancia.
   - Llama a view.dispatch(request, *args, **kwargs) que enruta al método HTTP correcto (get(), post(), etc.).
Sin .as_view(), pasarías la clase misma y Django no sabría cómo instanciarla.
"""

urlpatterns = [
    path('', views.BlogHomeView.as_view(), name='blog_home'),
    # Post CRUD operations
    path('posts/create/', views.PostCreateView.as_view(), name='create-post'),
    path('posts/<slug:slug>/', views.PostDetailView.as_view(), name='post-detail'),
    path('posts/<slug:slug>/edit/', views.PostUpdateView.as_view(), name='edit-post'),
    path('posts/<slug:slug>/delete/', views.PostDeleteView.as_view(), name='delete-post'),
    path('posts/<slug:slug>/like/', views.ToggleLikeView.as_view(), name='toggle-like'),

    # Category CRUD operations
    path("categories/create/", views.CategoryCreateView.as_view(), name="create-category"),

    # Tags CRUD operations
    path("tags/create/", views.TagCreateView.as_view(), name="create-tag"),
    
    # Comment operations
    path("comments/<int:comment_id>/delete/", views.CommentView.as_view(), name="delete-comment"),
]