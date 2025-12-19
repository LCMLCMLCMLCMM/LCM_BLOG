from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import password_validation
from .models import User, Post, Comment, Category, Tag


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=False)
    age = forms.IntegerField(required=False)
    gender = forms.ChoiceField(choices=[('', '保密'), ('male', '男'), ('female', '女')], required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'age', 'gender')


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=False)
    age = forms.IntegerField(required=False)
    gender = forms.ChoiceField(choices=[('', '保密'), ('male', '男'), ('female', '女')], required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'age', 'gender', 'signature', 'avatar')


class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label='当前密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password1 = forms.CharField(
        label='新密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label='确认新密码',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError("当前密码不正确")
        return old_password

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("两次输入的新密码不一致")
        return password2

    def save(self, commit=True):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class PostForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="选择分类"
    )
    
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    class Meta:
        model = Post
        fields = ('title', 'content', 'category', 'tags')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('content',)
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': '输入您的评论...',
                'required': 'required'
            }),
        }