from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, UpdateView
from .forms import RegisterForm, ProfileForm
from .models import Profile

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Auto-login after registration
            return redirect('home')  # Replace 'home' with your desired redirect URL. I think Blog.
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('home')
    return redirect('home')




#PROFILE READ
class ProfileView(LoginRequiredMixin, DetailView):
    model = Profile
    template_name = 'registration/profile_detail.html'

    def get_object(self):
        return self.request.user.profile

#PROFILE UPDATE
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = 'registration/profile_form.html'

    def get_object(self):
        return self.request.user.profile

    def get_success_url(self):
        return reverse("profile")
