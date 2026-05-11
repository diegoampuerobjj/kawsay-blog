from django import forms
from .models import Post, Category, Tag, Comment

class DateInput(forms.DateInput):
    input_type = 'date'


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'category', 'excerpt', 'content', 'tags', 'featured_image', 'published_at']
        widgets = {
            'published_at': DateInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name']

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['user', 'content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Share your thoughts...',
                'class': 'form-control'
            })
        }
