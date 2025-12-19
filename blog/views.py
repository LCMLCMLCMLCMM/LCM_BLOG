from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.db.models import Q, Max, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from .models import Post, User, Comment, Report, Friendship, PrivateMessage, Category, Tag, Notification
from .forms import CustomUserCreationForm, UserUpdateForm, PostForm, CommentForm, PasswordChangeForm


@cache_page(60 * 5)  # 缓存5分钟
def home(request):
    """
    主页视图
    """
    # 获取所有文章，按日期倒序排列
    cache_key = 'home_posts'
    all_posts = cache.get(cache_key)
    
    if all_posts is None:
        all_posts = Post.objects.select_related('author', 'category').prefetch_related('tags').order_by('-date_posted')
        cache.set(cache_key, all_posts, 60 * 5)  # 缓存5分钟
    
    # 分页处理
    paginator = Paginator(all_posts, 10)  # 每页显示10篇文章
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 获取分类和标签
    categories = Category.objects.annotate(posts_count=Count('posts'))
    tags = Tag.objects.annotate(posts_count=Count('posts'))[:20]
    
    # 用户统计
    users_count = User.objects.count()
    
    # 未读通知数
    unread_notifications_count = 0
    if request.user.is_authenticated:
        unread_notifications_count = request.user.notifications.filter(is_read=False).count()
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'tags': tags,
        'users_count': users_count,
        'unread_notifications_count': unread_notifications_count,
    }
    
    return render(request, 'blog/home.html', context)


def post_detail(request, post_id):
    """
    文章详情视图
    """
    cache_key = f'post_{post_id}'
    post_data = cache.get(cache_key)
    
    if post_data is None:
        post = get_object_or_404(Post.objects.select_related('author', 'category').prefetch_related('tags'), id=post_id)
        post_data = {
            'post': post,
            'comments': post.comments.filter(parent=None).select_related('author').prefetch_related('replies__author').order_by('-date_posted')
        }
        cache.set(cache_key, post_data, 60 * 10)  # 缓存10分钟
    else:
        post = post_data['post']
        comments = post_data['comments']
    
    # 处理评论表单
    if request.method == 'POST' and request.user.is_authenticated:
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            
            # 清除相关缓存
            cache.delete(cache_key)
            cache.delete('home_posts')
            
            # 创建通知（如果不是自己的文章）
            if post.author != request.user:
                Notification.objects.create(
                    recipient=post.author,
                    sender=request.user,
                    notification_type='comment',
                    content=f'{request.user.username} 评论了您的文章 "{post.title}"',
                    related_post=post
                )
            
            messages.success(request, '评论发表成功')
            return redirect('post_detail', post_id=post.id)
    else:
        form = CommentForm()
    
    return render(request, 'blog/post.html', {
        'post': post,
        'comments': post.comments.filter(parent=None).select_related('author').prefetch_related('replies__author').order_by('-date_posted'),
        'form': form
    })


def user_home(request, user_id):
    """
    用户主页视图
    """
    user = get_object_or_404(User, id=user_id)
    cache_key = f'user_posts_{user_id}'
    user_posts = cache.get(cache_key)
    
    if user_posts is None:
        user_posts = Post.objects.filter(author=user).order_by('-date_posted')
        cache.set(cache_key, user_posts, 60 * 5)  # 缓存5分钟
    
    return render(request, 'blog/user_home.html', {'user': user, 'user_posts': user_posts})


def user_login(request):
    """
    用户登录视图
    """
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_banned:
                messages.error(request, '用户已被封禁')
                return render(request, 'blog/banned.html')
            
            login(request, user)
            # 记录登录IP
            user.last_login_ip = request.META.get('REMOTE_ADDR')
            user.save()
            
            # 检查是否有保存的偏好设置
            theme_preference = request.COOKIES.get('theme_preference')
            layout_preference = request.COOKIES.get('layout_preference')
            
            if theme_preference:
                user.theme_preference = theme_preference
                user.save()
            
            next_page = request.GET.get('next', 'home')
            response = redirect(next_page)
            
            # 如果用户有布局偏好，设置cookie
            if layout_preference:
                response.set_cookie('layout_preference', layout_preference, max_age=30*24*60*60)
            
            return response
        else:
            messages.error(request, '用户名或密码错误')
    
    return render(request, 'blog/login.html')


def user_logout(request):
    """
    用户登出视图
    """
    # 保存用户的主题偏好到cookie
    response = redirect('home')
    if request.user.is_authenticated:
        response.set_cookie('theme_preference', request.user.theme_preference, max_age=30*24*60*60)
    
    logout(request)
    return response


def register(request):
    """
    用户注册视图
    """
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.role = 'user'
            user.save()
            
            # 设置默认偏好
            layout_preference = request.COOKIES.get('layout_preference', 'default')
            user.theme_preference = request.COOKIES.get('theme_preference', 'light')
            user.save()
            
            messages.success(request, '注册成功，请登录')
            response = redirect('login')
            response.set_cookie('layout_preference', layout_preference, max_age=30*24*60*60)
            return response
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'blog/register.html', {'form': form})


@login_required
def create_post(request):
    """
    创建文章视图
    """
    if request.user.is_banned:
        messages.error(request, '用户已被封禁')
        return render(request, 'blog/banned.html')
    
    if request.user.is_muted:
        messages.error(request, '用户已被禁言，无法发表文章')
        return redirect('home')
    
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()  # 保存多对多关系（标签）
            
            # 清除首页缓存
            cache.delete('home_posts')
            
            messages.success(request, '文章发表成功')
            return redirect('post_detail', post_id=post.id)
    else:
        form = PostForm()
    
    return render(request, 'blog/create_post.html', {'form': form})


@login_required
def edit_post(request, post_id):
    """
    编辑文章视图
    """
    post = get_object_or_404(Post, id=post_id)
    
    # 检查权限：只能编辑自己的文章或者管理员可以编辑所有文章
    if post.author != request.user and not request.user.is_administrator:
        messages.error(request, '您没有权限编辑此文章')
        return redirect('post_detail', post_id=post.id)
    
    if request.user.is_banned:
        messages.error(request, '用户已被封禁')
        return render(request, 'blog/banned.html')
    
    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            
            # 清除相关缓存
            cache.delete(f'post_{post_id}')
            cache.delete('home_posts')
            
            messages.success(request, '文章更新成功')
            return redirect('post_detail', post_id=post.id)
    else:
        form = PostForm(instance=post)
    
    return render(request, 'blog/edit_post.html', {'form': form, 'post': post})


@login_required
def delete_post(request, post_id):
    """
    删除文章视图
    """
    post = get_object_or_404(Post, id=post_id)
    
    # 检查权限：只能删除自己的文章或者管理员可以删除所有文章
    if post.author != request.user and not request.user.is_administrator:
        messages.error(request, '您没有权限删除此文章')
        return redirect('post_detail', post_id=post.id)
    
    if request.user.is_banned:
        messages.error(request, '用户已被封禁')
        return render(request, 'blog/banned.html')
    
    if request.method == 'POST':
        # 清除相关缓存
        cache.delete(f'post_{post_id}')
        cache.delete('home_posts')
        
        post.delete()
        messages.success(request, '文章删除成功')
        return redirect('home')
    
    return render(request, 'blog/delete_post.html', {'post': post})


@login_required
def profile(request):
    """
    用户资料视图
    """
    if request.method == 'POST':
        # 检查是否是密码修改请求
        if 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # 更新会话以避免登出
                messages.success(request, '密码修改成功')
                return redirect('profile')
            else:
                # 密码修改失败，显示错误信息
                context = {
                    'form': UserUpdateForm(instance=request.user),
                    'password_form': password_form,
                    'layout_preference': request.COOKIES.get('layout_preference', 'default')
                }
                return render(request, 'blog/profile.html', context)
        else:
            # 处理用户资料更新
            form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
            if form.is_valid():
                form.save()
                
                # 保存布局偏好到cookie
                layout_preference = request.POST.get('layout_preference', 'default')
                response = redirect('profile')
                response.set_cookie('layout_preference', layout_preference, max_age=30*24*60*60)
                
                messages.success(request, '您的资料已更新')
                return response
    else:
        form = UserUpdateForm(instance=request.user)
        password_form = PasswordChangeForm(request.user)
    
    # 获取用户的布局偏好
    layout_preference = request.COOKIES.get('layout_preference', 'default')
    
    return render(request, 'blog/profile.html', {
        'form': form,
        'password_form': password_form,
        'layout_preference': layout_preference
    })


@login_required
def add_comment(request, post_id):
    """
    添加评论视图
    """
    post = get_object_or_404(Post, id=post_id)
    
    if request.user.is_banned or request.user.is_muted:
        messages.error(request, '您无法发表评论')
        return redirect('post_detail', post_id=post.id)
    
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            
            # 如果是回复评论
            parent_id = request.POST.get('parent_id')
            if parent_id:
                parent_comment = get_object_or_404(Comment, id=parent_id)
                comment.parent = parent_comment
                
                # 创建回复通知
                if parent_comment.author != request.user:
                    Notification.objects.create(
                        recipient=parent_comment.author,
                        sender=request.user,
                        notification_type='reply',
                        content=f'{request.user.username} 回复了您的评论',
                        related_post=post,
                        related_comment=parent_comment
                    )
                
            comment.save()
            
            # 清除文章缓存
            cache.delete(f'post_{post_id}')
            
            messages.success(request, '评论发表成功')
    
    return redirect('post_detail', post_id=post.id)


def search(request):
    """
    搜索视图
    """
    query = request.GET.get('q')
    posts = []
    users = []
    
    if query:
        # 搜索文章（标题和内容）
        posts = Post.objects.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        ).select_related('author').order_by('-date_posted')
        
        # 搜索用户
        users = User.objects.filter(
            Q(username__icontains=query)
        ).order_by('username')
    
    context = {
        'query': query,
        'posts': posts,
        'users': users,
    }
    
    return render(request, 'blog/search_results.html', context)


def category_view(request, category_id):
    """
    分类文章视图
    """
    category = get_object_or_404(Category, id=category_id)
    posts = Post.objects.filter(category=category).select_related('author').order_by('-date_posted')
    
    # 分页处理
    paginator = Paginator(posts, 10)  # 每页显示10篇文章
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    
    return render(request, 'blog/category.html', context)


def tag_view(request, tag_id):
    """
    标签文章视图
    """
    tag = get_object_or_404(Tag, id=tag_id)
    posts = Post.objects.filter(tags=tag).select_related('author').order_by('-date_posted')
    
    # 分页处理
    paginator = Paginator(posts, 10)  # 每页显示10篇文章
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tag': tag,
        'page_obj': page_obj,
    }
    
    return render(request, 'blog/tag.html', context)


@login_required
def follow_user(request, user_id):
    """
    关注用户
    """
    user_to_follow = get_object_or_404(User, id=user_id)
    
    # 不能关注自己
    if user_to_follow == request.user:
        messages.error(request, '不能关注自己')
        return redirect('user_home', user_id=user_id)
    
    # 检查是否已经关注
    friendship, created = Friendship.objects.get_or_create(
        follower=request.user,
        followed=user_to_follow,
        defaults={'status': 'accepted'}
    )
    
    if created:
        # 创建关注通知
        Notification.objects.create(
            recipient=user_to_follow,
            sender=request.user,
            notification_type='follow',
            content=f'{request.user.username} 关注了您'
        )
        messages.success(request, f'成功关注 {user_to_follow.username}')
    else:
        messages.info(request, f'您已经关注了 {user_to_follow.username}')
    
    return redirect('user_home', user_id=user_id)


@login_required
def unfollow_user(request, user_id):
    """
    取消关注用户
    """
    user_to_unfollow = get_object_or_404(User, id=user_id)
    
    # 不能取消关注自己
    if user_to_unfollow == request.user:
        messages.error(request, '不能取消关注自己')
        return redirect('user_home', user_id=user_id)
    
    # 删除关注关系
    Friendship.objects.filter(
        follower=request.user,
        followed=user_to_unfollow
    ).delete()
    
    messages.success(request, f'已取消关注 {user_to_unfollow.username}')
    return redirect('user_home', user_id=user_id)


@login_required
def send_message(request, user_id):
    """
    发送私信
    """
    recipient = get_object_or_404(User, id=user_id)
    
    # 不能给自己发消息
    if recipient == request.user:
        messages.error(request, '不能给自己发送消息')
        return redirect('user_home', user_id=user_id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            message = PrivateMessage.objects.create(
                sender=request.user,
                receiver=recipient,
                content=content
            )
            
            # 创建私信通知
            Notification.objects.create(
                recipient=recipient,
                sender=request.user,
                notification_type='message',
                content=f'{request.user.username} 给您发送了私信'
            )
            
            messages.success(request, '消息发送成功')
        else:
            messages.error(request, '消息内容不能为空')
    
    return redirect('user_home', user_id=user_id)


@login_required
def inbox(request):
    """
    收件箱
    """
    # 获取收到的消息
    received_messages = PrivateMessage.objects.filter(
        receiver=request.user
    ).select_related('sender').order_by('-timestamp')
    
    # 标记为已读
    PrivateMessage.objects.filter(
        receiver=request.user,
        is_read=False
    ).update(is_read=True)
    
    return render(request, 'blog/inbox.html', {
        'messages_list': received_messages
    })


@login_required
def chat_sessions(request):
    """
    私信会话列表
    """
    # 获取与当前用户相关的所有会话（作为发送者或接收者）
    sent_messages = PrivateMessage.objects.filter(sender=request.user).values('receiver').annotate(
        last_message_time=Max('timestamp')
    )
    received_messages = PrivateMessage.objects.filter(receiver=request.user).values('sender').annotate(
        last_message_time=Max('timestamp')
    )
    
    # 获取所有会话伙伴
    chat_partners = set()
    for msg in sent_messages:
        chat_partners.add(msg['receiver'])
    for msg in received_messages:
        chat_partners.add(msg['sender'])
    
    # 获取会话伙伴的详细信息和最后一条消息
    chats = []
    for partner_id in chat_partners:
        partner = User.objects.get(id=partner_id)
        
        # 获取最后一条消息
        last_message = PrivateMessage.objects.filter(
            Q(sender=request.user, receiver=partner) | Q(sender=partner, receiver=request.user)
        ).order_by('-timestamp').first()
        
        # 获取未读消息数量
        unread_count = PrivateMessage.objects.filter(
            sender=partner,
            receiver=request.user,
            is_read=False
        ).count()
        
        chats.append({
            'partner': partner,
            'last_message': last_message,
            'unread_count': unread_count
        })
    
    # 按最后消息时间排序
    chats.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else timezone.now(), reverse=True)
    
    return render(request, 'blog/chat_sessions.html', {'chats': chats})


@login_required
def chat_history(request, user_id):
    """
    与特定用户的聊天历史
    """
    partner = get_object_or_404(User, id=user_id)
    
    # 获取聊天历史
    messages_history = PrivateMessage.objects.filter(
        Q(sender=request.user, receiver=partner) | Q(sender=partner, receiver=request.user)
    ).order_by('timestamp')
    
    # 标记对方发送给我的消息为已读
    PrivateMessage.objects.filter(
        sender=partner,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)
    
    # 获取用户的聊天布局偏好
    chat_layout = request.COOKIES.get('chat_layout', 'default')
    
    return render(request, 'blog/chat_history.html', {
        'partner': partner,
        'messages_history': messages_history,
        'chat_layout': chat_layout
    })


@login_required
@require_http_methods(["POST"])
def send_chat_message(request, user_id):
    """
    发送聊天消息
    """
    partner = get_object_or_404(User, id=user_id)
    content = request.POST.get('content')
    
    if content:
        message = PrivateMessage.objects.create(
            sender=request.user,
            receiver=partner,
            content=content
        )
        
        # 创建私信通知
        Notification.objects.create(
            recipient=partner,
            sender=request.user,
            notification_type='message',
            content=f'{request.user.username} 给您发送了私信'
        )
        
        # 如果是AJAX请求，返回JSON响应
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # 获取聊天布局偏好并返回给前端
            chat_layout = request.COOKIES.get('chat_layout', 'default')
            return JsonResponse({
                'status': 'success',
                'layout': chat_layout,
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'sender': {
                        'username': message.sender.username,
                        'avatar_url': message.sender.get_avatar_url()
                    }
                }
            })
    
    # 重定向回聊天页面
    return redirect('chat_history', user_id=user_id)


@login_required
def notifications(request):
    """
    用户通知页面
    """
    # 获取用户的通知
    user_notifications = Notification.objects.filter(recipient=request.user)
    
    # 分页处理
    paginator = Paginator(user_notifications, 20)  # 每页显示20条通知
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 标记所有未读通知为已读
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    return render(request, 'blog/notifications.html', {'page_obj': page_obj})


@login_required
def report_content(request):
    """
    举报内容
    """
    if request.method == 'POST':
        post_id = request.POST.get('post_id')
        comment_id = request.POST.get('comment_id')
        reason = request.POST.get('reason')
        
        if not reason:
            messages.error(request, '请填写举报原因')
            if post_id:
                return redirect('post_detail', post_id=post_id)
            else:
                return redirect('home')
        
        # 创建举报
        report = Report(
            reporter=request.user,
            reason=reason
        )
        
        if post_id:
            report.post = get_object_or_404(Post, id=post_id)
        elif comment_id:
            report.comment = get_object_or_404(Comment, id=comment_id)
        
        report.save()
        messages.success(request, '举报已提交，管理员会尽快处理')
        
        if post_id:
            return redirect('post_detail', post_id=post_id)
    
    return redirect('home')


@login_required
def toggle_theme(request):
    """
    切换主题（深色/浅色模式）
    """
    if request.user.is_authenticated:
        user = request.user
        user.theme_preference = 'dark' if user.theme_preference == 'light' else 'light'
        user.save()
    else:
        # 对于未登录用户，使用Cookie存储主题偏好
        current_theme = request.COOKIES.get('theme', 'light')
        new_theme = 'dark' if current_theme == 'light' else 'light'
        response = redirect(request.META.get('HTTP_REFERER', 'home'))
        response.set_cookie('theme', new_theme, max_age=30*24*60*60)  # 30天
        return response
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def set_layout_preference(request):
    """
    设置布局偏好
    """
    if request.method == 'POST':
        layout = request.POST.get('layout', 'default')
        response = redirect(request.META.get('HTTP_REFERER', 'home'))
        response.set_cookie('layout_preference', layout, max_age=30*24*60*60)  # 30天
        
        # 如果用户已登录，也保存到用户设置中
        if request.user.is_authenticated:
            request.user.layout_preference = layout
            request.user.save()
        
        return response
    return redirect('home')


def set_chat_layout(request):
    """
    设置聊天布局
    """
    if request.method == 'POST':
        layout = request.POST.get('chat_layout', 'default')
        response = redirect(request.META.get('HTTP_REFERER', 'home'))
        response.set_cookie('chat_layout', layout, max_age=30*24*60*60)  # 30天
        return response
    return redirect('home')


@login_required
def admin_panel(request):
    """
    管理员面板
    """
    # 检查用户权限
    if not request.user.is_administrator:
        messages.error(request, '您没有权限访问管理员面板')
        return redirect('home')
    
    # 获取统计数据
    users_count = User.objects.count()
    posts_count = Post.objects.count()
    comments_count = Comment.objects.count()
    reports_pending = Report.objects.filter(status='pending').count()
    
    # 获取待处理举报
    pending_reports = Report.objects.filter(status='pending').select_related('reporter', 'post', 'comment')
    
    # 获取所有用户（仅站长可以看到所有用户）
    users = User.objects.all() if request.user.is_master else None
    
    context = {
        'users_count': users_count,
        'posts_count': posts_count,
        'comments_count': comments_count,
        'reports_pending': reports_pending,
        'pending_reports': pending_reports,
        'users': users,
    }
    
    return render(request, 'blog/admin_panel.html', context)


@login_required
def handle_report(request, report_id, action):
    """
    处理举报
    """
    if not request.user.is_administrator:
        messages.error(request, '您没有权限处理举报')
        return redirect('home')
    
    report = get_object_or_404(Report, id=report_id)
    
    # 站长可以处理所有举报，管理员只能处理普通用户的举报
    if not request.user.is_master and report.post and report.post.author.is_administrator:
        messages.error(request, '您没有权限处理此举报')
        return redirect('admin_panel')
    
    if action == 'resolve':
        report.status = 'resolved'
        messages.success(request, '举报已标记为已解决')
    elif action == 'dismiss':
        report.status = 'dismissed'
        messages.success(request, '举报已驳回')
    
    report.save()
    return redirect('admin_panel')


@login_required
def toggle_user_ban(request, user_id):
    """
    封禁/解封用户
    """
    if not request.user.is_administrator:
        messages.error(request, '您没有权限执行此操作')
        return redirect('home')
    
    user = get_object_or_404(User, id=user_id)
    
    # 不能操作自己
    if user == request.user:
        messages.error(request, '不能对自己执行此操作')
        return redirect('admin_panel')
    
    # 管理员不能操作站长
    if not request.user.is_master and user.is_master:
        messages.error(request, '您没有权限操作站长')
        return redirect('admin_panel')
    
    user.is_banned = not user.is_banned
    user.save()
    
    action = "封禁" if user.is_banned else "解封"
    messages.success(request, f'用户 {user.username} 已被{action}')
    return redirect('admin_panel')


@login_required
def toggle_user_mute(request, user_id):
    """
    要言/解除禁言用户
    """
    if not request.user.is_administrator:
        messages.error(request, '您没有权限执行此操作')
        return redirect('home')
    
    user = get_object_or_404(User, id=user_id)
    
    # 不能操作自己
    if user == request.user:
        messages.error(request, '不能对自己执行此操作')
        return redirect('admin_panel')
    
    # 管理员不能操作站长
    if not request.user.is_master and user.is_master:
        messages.error(request, '您没有权限操作站长')
        return redirect('admin_panel')
    
    user.is_muted = not user.is_muted
    user.save()
    
    action = "禁言" if user.is_muted else "解除禁言"
    messages.success(request, f'用户 {user.username} 已被{action}')
    return redirect('admin_panel')


@login_required
def toggle_admin(request, user_id):
    """
    添加/撤销管理员权限
    """
    # 只有站长可以操作管理员权限
    if not request.user.is_master:
        messages.error(request, '您没有权限执行此操作')
        return redirect('home')
    
    user = get_object_or_404(User, id=user_id)
    
    # 不能操作自己
    if user == request.user:
        messages.error(request, '不能对自己执行此操作')
        return redirect('admin_panel')
    
    # 不能操作站长
    if user.is_master:
        messages.error(request, '不能改变站长的权限')
        return redirect('admin_panel')
    
    if user.is_administrator and not user.is_master:
        user.role = 'user'
        messages.success(request, f'用户 {user.username} 的管理员权限已被撤销')
    elif user.is_regular_user:
        user.role = 'admin'
        messages.success(request, f'用户 {user.username} 已被授予管理员权限')
    
    user.save()
    return redirect('admin_panel')


@login_required
def delete_account(request):
    """
    注销账户视图
    """
    if request.method == 'POST':
        # 确认用户真的想要删除账户
        confirm = request.POST.get('confirm')
        if confirm == 'yes':
            user = request.user
            logout(request)  # 先登出用户
            user.delete()    # 然后删除用户账户
            messages.success(request, '您的账户已成功注销')
            return redirect('home')
        else:
            messages.error(request, '请确认您要注销账户')
            return redirect('profile')
    
    return render(request, 'blog/delete_account.html')
