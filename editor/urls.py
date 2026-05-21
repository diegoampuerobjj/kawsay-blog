from django.urls import path
from . import views

app_name = 'editor'

urlpatterns = [
    # Create & Edit
    path('posts/create/', views.EditorCreateView.as_view(), name='create'),
    path('posts/<slug:slug>/edit/', views.EditorUpdateView.as_view(), name='edit'),

    # Publish/Unpublish
    path('posts/<slug:slug>/publish/', views.PublishView.as_view(), name='publish'),

    # Versions
    path('posts/<slug:slug>/versions/', views.VersionHistoryView.as_view(), name='version-history'),
    path('posts/<slug:slug>/versions/<int:version_number>/restore/', views.RestoreVersionView.as_view(), name='restore-version'),

    # Preview (renders Markdown → HTML)
    path('posts/<slug:slug>/preview/', views.PreviewView.as_view(), name='preview'),
]
    