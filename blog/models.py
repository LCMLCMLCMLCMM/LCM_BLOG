from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.crypto import get_random_string
import hashlib
import base64
import os
from PIL import Image
from io import BytesIO
import markdown
import bleach

class User(AbstractUser):
    ROLE_CHOICES = (
        ('user', '普通用户'),
        ('admin', '管理员'),
        ('master', '站长'),
    )
    
    firebase_uid = models.CharField(max_length=120, unique=True, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    is_banned = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    theme_preference = models.CharField(max_length=10, default='light')
    layout_preference = models.CharField(max_length=20, default='default')
    signature = models.CharField(max_length=200, blank=True, default='')
    avatar_url = models.URLField(blank=True, default='')
    last_login_ip = models.CharField(max_length=45, blank=True, default='')
    contact_info = models.TextField(blank=True, default='')
    age = models.IntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    # 修改头像字段为TextField以存储base64编码的图像
    avatar = models.TextField(blank=True, null=True)  # 存储base64编码的图像数据

    def __str__(self):
        return self.username
        
    def save(self, *args, **kwargs):
        # 如果是新用户且没有设置角色，默认设为普通用户
        if not self.pk and not self.role:
            self.role = 'user'
        super().save(*args, **kwargs)
        
    def get_avatar_url(self):
        """获取用户头像URL - 如果是base64编码的头像则返回data URL，否则返回原始逻辑"""
        if self.avatar:
            # 如果avatar是base64编码的数据，直接返回data URL
            if self.avatar.startswith('data:image'):
                return self.avatar
            else:
                # 如果只是base64字符串，添加data URL前缀
                return f'data:image/png;base64,{self.avatar}'
        elif self.avatar_url:
            return self.avatar_url
        else:
            # 使用Gravatar作为默认头像
            email_hash = hashlib.md5(self.email.lower().encode('utf-8')).hexdigest() if self.email else '00000000000000000000000000000000'
            return f'https://www.gravatar.com/avatar/{email_hash}?d=identicon'
            
    def set_avatar_from_file(self, image_file):
        """从上传的文件设置base64编码的头像"""
        try:
            # 使用Pillow处理图像
            img = Image.open(image_file)
            # 转换为RGB模式（如果需要）
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            # 调整大小以优化存储
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            # 保存到内存中的BytesIO对象
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            # 获取图像数据并转换为base64
            img_str = base64.b64encode(buffer.getvalue()).decode()
            self.avatar = img_str
        except Exception as e:
            print(f"Error processing avatar image: {e}")
            raise

    @property
    def is_master(self):
        """判断是否为站长"""
        return self.role == 'master'
        
    @property
    def is_administrator(self):
        """判断是否为管理员（包括站长）"""
        return self.role in ['admin', 'master']
        
    @property
    def is_regular_user(self):
        """判断是否为普通用户"""
        return self.role == 'user'


class Category(models.Model):
    """文章分类"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"


class Tag(models.Model):
    """文章标签"""
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    date_posted = models.DateTimeField(default=timezone.now)
    is_update_log = models.BooleanField(default=False)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')

    def __str__(self):
        return self.title

    def get_rendered_content(self):
        """渲染文章内容，支持Markdown和安全的HTML，包括base64图片"""
        # 检查内容是否包含base64图片（以data:image/开头的img标签）
        # 如果是，我们直接使用HTML，但要清理其他不安全的内容
        if '<img src="data:image/' in self.content:
            # 内容包含base64图片，直接使用HTML，但要清理其他不安全的内容
            allowed_tags = [
                'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'blockquote', 'pre', 'code', 'hr', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'a', 'img',
                'div', 'span', 'figure', 'figcaption'
            ]
            allowed_attributes = {
                'a': ['href', 'title', 'target'],
                'img': ['src', 'alt', 'title', 'width', 'height', 'class'],  # 确保允许class属性
                'div': ['class'],
                'span': ['class'],
                'p': ['class'],
                'code': ['class'],
                'pre': ['class'],
                'td': ['style'],
                'th': ['style'],
                'table': ['style'],
                'tr': ['style']
            }
            clean_html = bleach.clean(self.content, tags=allowed_tags, attributes=allowed_attributes, strip=True)
            return clean_html
        else:
            # 使用Markdown转换
            md = markdown.markdown(self.content, extensions=[
                'extra',      # 包含表格、代码块等
                'codehilite', # 代码高亮
                'toc',        # 目录
                'nl2br'       # 换行符转为<br>
            ])
            
            # 使用bleach清理HTML，防止XSS攻击
            allowed_tags = [
                'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'blockquote', 'pre', 'code', 'hr', 'table', 'thead', 'tbody', 'tr', 'td', 'th', 'a', 'img',
                'div', 'span', 'figure', 'figcaption'
            ]
            allowed_attributes = {
                'a': ['href', 'title', 'target'],
                'img': ['src', 'alt', 'title', 'width', 'height', 'class'],  # 确保允许class属性
                'div': ['class'],
                'span': ['class'],
                'p': ['class'],
                'code': ['class'],
                'pre': ['class']
            }
            clean_html = bleach.clean(md, tags=allowed_tags, attributes=allowed_attributes, strip=True)
            return clean_html

    class Meta:
        ordering = ['-date_posted']


class Comment(models.Model):
    content = models.TextField()
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='replies')
    date_posted = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.author.username}: {self.content[:20]}...'
    
    def get_rendered_content(self):
        """渲染评论内容，支持Markdown和安全的HTML"""
        # 先转换Markdown
        md = markdown.markdown(self.content, extensions=['nl2br'])  # 简单的换行转换
        
        # 使用bleach清理HTML，防止XSS攻击
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'code', 'pre', 'a']
        allowed_attributes = {
            'a': ['href', 'title'],
        }
        clean_html = bleach.clean(md, tags=allowed_tags, attributes=allowed_attributes, strip=True)
        return clean_html

    class Meta:
        ordering = ['-date_posted']


class Report(models.Model):
    STATUS_CHOICES = (
        ('pending', '待处理'),
        ('resolved', '已解决'),
        ('dismissed', '已驳回'),
    )
    
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, blank=True, null=True, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, blank=True, null=True, related_name='reports')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    date_reported = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'Report by {self.reporter.username}'


class Friendship(models.Model):
    STATUS_CHOICES = (
        ('accepted', '已接受'),
        ('pending', '待处理'),
        ('rejected', '已拒绝'),
    )
    
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='accepted')

    def __str__(self):
        return f'{self.follower.username} -> {self.followed.username}'

    class Meta:
        unique_together = ('follower', 'followed')


class PrivateMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.sender.username} -> {self.receiver.username}: {self.content[:20]}...'


class Notification(models.Model):
    """用户通知"""
    NOTIFICATION_TYPES = (
        ('comment', '评论'),
        ('reply', '回复'),
        ('follow', '关注'),
        ('message', '私信'),
        ('system', '系统通知'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    related_post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    related_comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f'Notification for {self.recipient.username}: {self.content[:30]}...'

    class Meta:
        ordering = ['-created_at']


class InviteCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    used_at = models.DateTimeField(blank=True, null=True)
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    used_ip = models.CharField(max_length=45, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.code

    @property
    def is_used(self):
        return self.used_at is not None
        
    def save(self, *args, **kwargs):
        # 如果没有提供邀请码，则自动生成一个
        if not self.code:
            self.code = get_random_string(20)
        super().save(*args, **kwargs)