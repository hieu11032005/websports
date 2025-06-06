from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import or_, desc, func
from app import db
from models import User, Article, Category, Comment, Tag, Advertisement, SiteStats
from forms import LoginForm, RegisterForm, ProfileForm, ArticleForm, CommentForm, SearchForm, CategoryForm
from utils import slugify, save_uploaded_file, format_datetime, time_ago, process_tags, search_articles

# Tạo các Blueprint
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__)
admin_bp = Blueprint('admin', __name__)
api_bp = Blueprint('api', __name__)

# ========== MAIN ROUTES ==========

@main_bp.route('/')
def index():
    """Trang chủ hiển thị tin tức mới nhất"""
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    # Lấy bài viết nổi bật
    featured_articles = Article.query.filter_by(is_published=True, is_featured=True)\
        .order_by(Article.published_at.desc()).limit(3).all()
    
    # Lấy bài viết mới nhất với phân trang
    articles = Article.query.filter_by(is_published=True)\
        .order_by(Article.published_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # Lấy danh mục
    categories = Category.query.filter_by(is_active=True).all()
    
    # Lấy quảng cáo
    ads_header = Advertisement.query.filter_by(position='header', is_active=True).first()
    ads_sidebar = Advertisement.query.filter_by(position='sidebar', is_active=True).limit(3).all()
    
    return render_template('index.html', 
                         featured_articles=featured_articles,
                         articles=articles,
                         categories=categories,
                         ads_header=ads_header,
                         ads_sidebar=ads_sidebar)

@main_bp.route('/category/<slug>')
def category(slug):
    """Trang danh mục tin tức"""
    category = Category.query.filter_by(slug=slug, is_active=True).first_or_404()
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    # Lấy bài viết theo danh mục
    articles = Article.query.filter_by(category_id=category.id, is_published=True)\
        .order_by(Article.published_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('category.html', category=category, articles=articles)

@main_bp.route('/article/<slug>')
def article_detail(slug):
    """Trang chi tiết bài viết"""
    article = Article.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Tăng lượt xem
    article.views_count += 1
    db.session.commit()
    
    # Lấy bình luận
    comments = Comment.query.filter_by(article_id=article.id, is_approved=True)\
        .order_by(Comment.created_at.desc()).all()
    
    # Lấy bài viết liên quan (cùng danh mục)
    related_articles = Article.query.filter_by(
        category_id=article.category_id, 
        is_published=True
    ).filter(Article.id != article.id)\
        .order_by(Article.published_at.desc()).limit(4).all()
    
    # Form bình luận
    comment_form = CommentForm()
    
    return render_template('article_detail.html', 
                         article=article, 
                         comments=comments,
                         related_articles=related_articles,
                         comment_form=comment_form)

@main_bp.route('/search')
def search():
    """Trang tìm kiếm"""
    form = SearchForm()
    articles = None
    query = request.args.get('query', '')
    category_id = request.args.get('category', 0, type=int)
    page = request.args.get('page', 1, type=int)
    
    if query:
        # Thực hiện tìm kiếm
        articles = search_articles(query, category_id, page, per_page=10)
    
    return render_template('search.html', form=form, articles=articles, 
                         query=query, category_id=category_id)

@main_bp.route('/add_comment/<int:article_id>', methods=['POST'])
@login_required
def add_comment(article_id):
    """Thêm bình luận"""
    article = Article.query.get_or_404(article_id)
    form = CommentForm()
    
    if form.validate_on_submit():
        comment = Comment(
            content=form.content.data,
            author_id=current_user.id,
            article_id=article_id
        )
        db.session.add(comment)
        db.session.commit()
        flash('Bình luận của bạn đã được thêm thành công!', 'success')
    else:
        flash('Có lỗi xảy ra khi thêm bình luận. Vui lòng thử lại.', 'error')
    
    return redirect(url_for('main.article_detail', slug=article.slug))

# ========== AUTH ROUTES ==========

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Đăng nhập"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            flash(f'Chào mừng {user.full_name or user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng!', 'error')
    
    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Đăng ký tài khoản"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Đăng ký thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Đăng xuất"""
    logout_user()
    flash('Bạn đã đăng xuất thành công!', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Trang hồ sơ cá nhân"""
    form = ProfileForm()
    
    if form.validate_on_submit():
        # Kiểm tra username và email trùng lặp
        if form.username.data != current_user.username:
            user = User.query.filter_by(username=form.username.data).first()
            if user:
                flash('Tên đăng nhập đã tồn tại!', 'error')
                return render_template('profile.html', form=form)
        
        if form.email.data != current_user.email:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                flash('Email đã được sử dụng!', 'error')
                return render_template('profile.html', form=form)
        
        # Cập nhật thông tin
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.full_name = form.full_name.data
        current_user.bio = form.bio.data
        
        # Xử lý upload avatar
        if form.avatar.data:
            avatar_filename = save_uploaded_file(form.avatar.data, 'avatars')
            if avatar_filename:
                current_user.avatar_url = avatar_filename
        
        db.session.commit()
        flash('Hồ sơ đã được cập nhật thành công!', 'success')
        return redirect(url_for('auth.profile'))
    
    # Điền dữ liệu hiện tại vào form
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.full_name.data = current_user.full_name
        form.bio.data = current_user.bio
    
    return render_template('profile.html', form=form)

# ========== ADMIN ROUTES ==========

@admin_bp.before_request
def require_admin():
    """Kiểm tra quyền admin cho tất cả route admin"""
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Bạn không có quyền truy cập trang này!', 'error')
        return redirect(url_for('main.index'))

@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    """Dashboard admin"""
    # Thống kê tổng quan
    total_articles = Article.query.count()
    total_users = User.query.count()
    total_comments = Comment.query.count()
    total_categories = Category.query.count()
    
    # Bài viết mới nhất
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(5).all()
    
    # Bình luận mới nhất
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()
    
    # Thống kê theo ngày (7 ngày gần đây)
    from datetime import date, timedelta
    stats = []
    for i in range(7):
        target_date = date.today() - timedelta(days=i)
        day_stats = SiteStats.query.filter_by(date=target_date).first()
        if day_stats:
            stats.append({
                'date': target_date.strftime('%d/%m'),
                'views': day_stats.page_views,
                'comments': day_stats.comments_count
            })
        else:
            stats.append({
                'date': target_date.strftime('%d/%m'),
                'views': 0,
                'comments': 0
            })
    stats.reverse()
    
    return render_template('admin/dashboard.html',
                         total_articles=total_articles,
                         total_users=total_users,
                         total_comments=total_comments,
                         total_categories=total_categories,
                         recent_articles=recent_articles,
                         recent_comments=recent_comments,
                         stats=stats)

@admin_bp.route('/articles')
def articles():
    """Quản lý bài viết"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category_id = request.args.get('category', 0, type=int)
    
    query = Article.query
    
    # Tìm kiếm
    if search:
        query = query.filter(Article.title.contains(search))
    
    # Lọc theo danh mục
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    articles = query.order_by(Article.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    categories = Category.query.all()
    
    return render_template('admin/articles.html', 
                         articles=articles, 
                         categories=categories,
                         search=search,
                         category_id=category_id)

@admin_bp.route('/article/new', methods=['GET', 'POST'])
@admin_bp.route('/article/edit/<int:id>', methods=['GET', 'POST'])
def article_form(id=None):
    """Form tạo/chỉnh sửa bài viết"""
    article = Article.query.get(id) if id else None
    form = ArticleForm()
    
    if form.validate_on_submit():
        if not article:
            article = Article(author_id=current_user.id)
            db.session.add(article)
        
        # Cập nhật thông tin bài viết
        article.title = form.title.data
        article.slug = slugify(form.title.data)
        article.summary = form.summary.data
        article.content = form.content.data
        article.category_id = form.category_id.data
        article.is_published = form.is_published.data
        article.is_featured = form.is_featured.data
        
        # Xử lý published_at
        if form.is_published.data and not article.published_at:
            article.published_at = datetime.utcnow()
        elif not form.is_published.data:
            article.published_at = None
        
        # Xử lý upload ảnh
        if form.featured_image.data:
            image_filename = save_uploaded_file(form.featured_image.data, 'articles')
            if image_filename:
                article.featured_image = image_filename
        
        # Xử lý tags
        if form.tags.data:
            tag_names = process_tags(form.tags.data)
            article.tags.clear()
            
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name, slug=slugify(tag_name))
                    db.session.add(tag)
                article.tags.append(tag)
        
        db.session.commit()
        
        action = 'tạo' if not id else 'cập nhật'
        flash(f'Bài viết đã được {action} thành công!', 'success')
        return redirect(url_for('admin.articles'))
    
    # Điền dữ liệu vào form khi chỉnh sửa
    if article and request.method == 'GET':
        form.title.data = article.title
        form.summary.data = article.summary
        form.content.data = article.content
        form.category_id.data = article.category_id
        form.is_published.data = article.is_published
        form.is_featured.data = article.is_featured
        form.tags.data = ', '.join([tag.name for tag in article.tags])
    
    return render_template('admin/article_form.html', form=form, article=article)

@admin_bp.route('/article/delete/<int:id>', methods=['POST'])
def delete_article(id):
    """Xóa bài viết"""
    article = Article.query.get_or_404(id)
    db.session.delete(article)
    db.session.commit()
    flash('Bài viết đã được xóa thành công!', 'success')
    return redirect(url_for('admin.articles'))

@admin_bp.route('/users')
def users():
    """Quản lý người dùng"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            or_(User.username.contains(search),
                User.email.contains(search),
                User.full_name.contains(search))
        )
    
    users = query.order_by(User.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/users.html', users=users, search=search)

# ========== API ROUTES ==========

@api_bp.route('/articles/popular')
def popular_articles():
    """API lấy bài viết phổ biến"""
    articles = Article.query.filter_by(is_published=True)\
        .order_by(Article.views_count.desc())\
        .limit(10).all()
    
    return jsonify([{
        'id': article.id,
        'title': article.title,
        'slug': article.slug,
        'view_count': article.views_count,
        'published_at': article.published_at.isoformat() if article.published_at else None
    } for article in articles])

@api_bp.route('/search/suggestions')
def search_suggestions():
    """API gợi ý tìm kiếm"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    # Tìm kiếm trong tiêu đề bài viết
    articles = Article.query.filter(
        Article.title.ilike(f'%{query}%'),
        Article.is_published == True
    ).limit(5).all()
    
    suggestions = [{'title': article.title, 'slug': article.slug} for article in articles]
    return jsonify(suggestions)

# ========== TEMPLATE FILTERS ==========

@main_bp.app_template_filter('datetime')
def datetime_filter(dt, format='%d/%m/%Y %H:%M'):
    """Filter để format datetime"""
    return format_datetime(dt, format)

@main_bp.app_template_filter('timeago')
def timeago_filter(dt):
    """Filter để hiển thị thời gian tương đối"""
    return time_ago(dt)

@main_bp.app_template_filter('truncate_html')
def truncate_html_filter(text, length=150):
    """Filter để cắt ngắn HTML content"""
    from utils import generate_excerpt
    return generate_excerpt(text, length)

# ========== CONTEXT PROCESSORS ==========

@main_bp.app_context_processor
def inject_global_data():
    """Inject dữ liệu global cho tất cả template"""
    categories = Category.query.filter_by(is_active=True).all()
    
    # Lấy bài viết phổ biến cho sidebar
    popular_articles = Article.query.filter_by(is_published=True)\
        .order_by(Article.views_count.desc()).limit(5).all()
    
    return {
        'global_categories': categories,
        'popular_articles': popular_articles
    }

# ========== ERROR HANDLERS ==========

@main_bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@main_bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500
