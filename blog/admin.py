from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from .models import User, Post, Comment, Report, Friendship, PrivateMessage, InviteCode


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = UserChangeForm.Meta.fields


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    
    list_display = ('username', 'email', 'role', 'is_banned', 'is_muted', 'is_staff', 'is_active')
    list_filter = ('role', 'is_banned', 'is_muted', 'is_staff', 'is_active')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('first_name', 'last_name', 'email', 'age', 'gender', 'signature', 'avatar')}),
        ('权限信息', {'fields': ('role', 'is_banned', 'is_muted', 'is_staff', 'is_active', 'is_superuser')}),
        ('重要日期', {'fields': ('last_login', 'date_joined', 'created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'role')}
        ),
    )
    
    search_fields = ('username', 'email')
    ordering = ('username',)


class CustomAdminSite(AdminSite):
    site_header = 'LCM\'s Blog 管理后台'
    site_title = 'LCM\'s Blog Admin'
    index_title = '欢迎使用 LCM\'s Blog 管理后台'


# 创建自定义AdminSite实例
custom_admin_site = CustomAdminSite(name='custom_admin')

# 注册模型到自定义管理后台
custom_admin_site.register(User, CustomUserAdmin)
custom_admin_site.register(Post)
custom_admin_site.register(Comment)
custom_admin_site.register(Report)
custom_admin_site.register(Friendship)
custom_admin_site.register(PrivateMessage)
custom_admin_site.register(InviteCode)

# 注册模型到默认管理后台
admin.site.register(User, CustomUserAdmin)
admin.site.register(Post)
admin.site.register(Comment)
admin.site.register(Report)
admin.site.register(Friendship)
admin.site.register(PrivateMessage)
admin.site.register(InviteCode)