from django.urls import path
from . import views

urlpatterns = [
    path('', views.blog_home, name='blog-home'),
    # Post CRUD operations
    path('posts/create/', views.create_post, name='create-post'),
    path('posts/<slug:slug>/', views.read_post, name='post-detail'),
    path('posts/<slug:slug>/edit/', views.update_post, name='edit-post'),
    path('posts/<slug:slug>/delete/', views.delete_post, name='delete-post'),
    path('posts/<slug:slug>/like/', views.toggle_like, name='toggle-like'),

    # Category CRUD operations
    path("categories/create/", views.create_category, name="create-category"),

    # Tags CRUD operations
    path("tags/create/", views.create_tag, name="create-tag"),
    
    # Comment operations
    path("comments/<int:comment_id>/delete/", views.delete_comment, name="delete-comment"),
]