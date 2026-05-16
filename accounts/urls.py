
from django.urls import path, include
from . import views
from .views import ProfileView, ProfileUpdateView

urlpatterns = [
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile-update'),
    path('', include('django.contrib.auth.urls')) 
]