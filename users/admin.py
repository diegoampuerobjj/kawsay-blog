from django.contrib import admin
from users.models import User, Profile
from blog.models import Post, Category, Comment, Like, Tag

admin.site.register([User, Profile, Post, Category, Comment, Like, Tag])
