from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import password_validation
from .models import User, Post, Comment, Category, Tag
import base64
from PIL import Image
from io import BytesIO


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=False)
    age = forms.IntegerField(required=False)
    gender = forms.ChoiceField(choices=[('', '保密'), ('male', '男'), ('female', '女')], required=False)
    avatar = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'age', 'gender', 'avatar')

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # 如果有头像上传，将其转换为base64
        if 'avatar' in self.cleaned_data and self.cleaned_data['avatar']:
            avatar_file = self.cleaned_data['avatar']
            user.set_avatar_from_file(avatar_file)
        
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=False)
    age = forms.IntegerField(required=False)
    gender = forms.ChoiceField(choices=[('', '保密'), ('male', '男'), ('female', '女')], required=False)
    avatar = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))
    
    class Meta:
        model = User
        fields = ('username', 'email', 'age', 'gender', 'signature', 'avatar')

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # 如果有新的头像上传，将其转换为base64
        if 'avatar' in self.cleaned_data and self.cleaned_data['avatar']:
            avatar_file = self.cleaned_data['avatar']
            user.set_avatar_from_file(avatar_file)
        
        if commit:
            user.save()
        return user


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
    
    # 添加图片上传字段
    image_upload = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
            'style': 'display: none;',
            'id': 'image-upload-input'
        })
    )
    
    class Meta:
        model = Post
        fields = ('title', 'content', 'category', 'tags')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }

    def clean_image_upload(self):
        image = self.cleaned_data.get('image_upload')
        if image:
            # 验证图片文件
            if image.content_type.startswith('image/'):
                # 使用PIL验证图片是否有效
                try:
                    img = Image.open(image)
                    img.verify()
                    # 重新打开图片以供后续处理
                    image.seek(0)
                except:
                    raise forms.ValidationError("上传的文件不是有效的图片")
            else:
                raise forms.ValidationError("请上传有效的图片文件")
        return image


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