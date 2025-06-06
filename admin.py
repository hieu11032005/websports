from flask import render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import func, desc, asc
from datetime import datetime, timedelta

from app import app, db
from models import (User, Article, Category, Comment, Tag, Advertisement, 
                   NewsletterSubscriber, SiteSettings)
from forms import ArticleForm, CategoryForm, AdvertisementForm
from utils import create_slug, admin_required

# Decorator kiểm tra quyền admin
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Dashboard quản trị"""
    # Thống kê tổng quan
    stats = {
        'total_articles': Article.query.count(),
        'published_articles': Article.query.filter_by(is_published=True).count(),
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_comments': Comment.query.count(),
        'pending_comments': Comment.query.filter_by(is_approved=False).count(),
        'total_categories': Category.query.count(),
        'newsletter_subscribers': NewsletterSubscriber.query.filter_by(is_active=True).count()
    }
    
    # Bài viết mới nhất
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(5).all()
    
    # Bài viết xem nhiều nhất tuần này
    week_ago = datetime.utcnow() - timedelta(days=7)
    popular_articles = Article.query.filter(
        Article.created_at >= week_ago
    ).order_by(Article.views_count.desc()).limit(5).all()
    
    # Comments cần duyệt
    pending_comments = Comment.query.filter_by(
        is_approved=False
    ).order_by(Comment.created_at.desc()).limit(5).all()
    
    # Thống kê theo tháng (6 tháng gần nhất)
    monthly_stats = []
    for i in range(6):
        date = datetime.utcnow() - timedelta(days=30 * i)
        start_month = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            end_month = datetime.utcnow()
        else:
            end_month = start_month.replace(day=28) + timedelta(days=4)
            end_month = end_month - timedelta(days=end_month.day)
        
        articles_count = Article.query.filter(
            Article.created_at >= start_month,
            Article.created_at <= end_month
        ).count()
        
        users_count = User.query.filter(
            User.created_at >= start_month,
            User.created_at <= end_month
        ).count()
        
        monthly_stats.append({
            'month': start_month.strftime('%m/%Y'),
            'articles': articles_count,
            'users': users_count
        })
    
    monthly_stats.reverse()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_articles=recent_articles,
                         popular_articles=popular_articles,
                         pending_comments=pending_comments,
                         monthly_stats=monthly_stats)

@app.route('/admin/articles')
@admin_required
def admin_articles():
    """Quản lý bài viết"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter theo trạng thái
    status = request.args.get('status', 'all')
    query = Article.query
    
    if status == 'published':
        query = query.filter_by(is_published=True)
    elif status == 'draft':
        query = query.filter_by(is_published=False)
    elif status == 'featured':
        query = query.filter_by(is_featured=True)
    
    # Filter theo danh mục
    category_id = request.args.get('category', 0, type=int)
    if category_id > 0:
        query = query.filter_by(category_id=category_id)
    
    # Filter theo tác giả
    author_id = request.args.get('author', 0, type=int)
    if author_id > 0:
        query = query.filter_by(author_id=author_id)
    
    articles = query.order_by(Article.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Danh sách danh mục và tác giả cho filter
    categories = Category.query.all()
    authors = User.query.filter_by(is_active=True).all()
    
    return render_template('admin/articles.html',
                         articles=articles,
                         categories=categories,
                         authors=authors,
                         current_status=status,
                         current_category=category_id,
                         current_author=author_id)

@app.route('/admin/articles/add', methods=['GET', 'POST'])
@admin_required
def admin_add_article():
    """Thêm bài viết mới"""
    form = ArticleForm()
    
    if form.validate_on_submit():
        # Tạo slug từ tiêu đề nếu không có
        slug = form.slug.data or create_slug(form.title.data)
        
        # Kiểm tra slug trùng lặp
        if Article.query.filter_by(slug=slug).first():
            flash('Slug URL đã được sử dụng. Vui lòng chọn slug khác.', 'error')
            return render_template('admin/add_article.html', form=form)
        
        article = Article(
            title=form.title.data,
            slug=slug,
            summary=form.summary.data,
            content=form.content.data,
            category_id=form.category_id.data,
            featured_image=form.featured_image.data,
            image_caption=form.image_caption.data,
            meta_description=form.meta_description.data,
            meta_keywords=form.meta_keywords.data,
            is_published=form.is_published.data,
            is_featured=form.is_featured.data,
            author_id=current_user.id
        )
        
        if form.is_published.data:
            article.published_at = datetime.utcnow()
        
        db.session.add(article)
        
        # Xử lý tags
        if form.tags.data:
            tag_names = [tag.strip() for tag in form.tags.data.split(',')]
            for tag_name in tag_names:
                if tag_name:
                    tag_slug = create_slug(tag_name)
                    tag = Tag.query.filter_by(slug=tag_slug).first()
                    if not tag:
                        tag = Tag(name=tag_name, slug=tag_slug)
                        db.session.add(tag)
                    article.tags.append(tag)
        
        # Cập nhật thống kê
        current_user.articles_count = Article.query.filter_by(author_id=current_user.id).count() + 1
        
        db.session.commit()
        
        flash('Đã thêm bài viết thành công!', 'success')
        return redirect(url_for('admin_articles'))
    
    return render_template('admin/add_article.html', form=form)

@app.route('/admin/articles/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_article(id):
    """Chỉnh sửa bài viết"""
    article = Article.query.get_or_404(id)
    form = ArticleForm(obj=article)
    
    # Set tags field
    form.tags.data = ', '.join([tag.name for tag in article.tags])
    
    if form.validate_on_submit():
        # Kiểm tra slug trùng lặp
        slug = form.slug.data or create_slug(form.title.data)
        existing = Article.query.filter(
            Article.slug == slug,
            Article.id != article.id
        ).first()
        
        if existing:
            flash('Slug URL đã được sử dụng. Vui lòng chọn slug khác.', 'error')
            return render_template('admin/edit_article.html', form=form, article=article)
        
        # Cập nhật thông tin
        article.title = form.title.data
        article.slug = slug
        article.summary = form.summary.data
        article.content = form.content.data
        article.category_id = form.category_id.data
        article.featured_image = form.featured_image.data
        article.image_caption = form.image_caption.data
        article.meta_description = form.meta_description.data
        article.meta_keywords = form.meta_keywords.data
        article.is_featured = form.is_featured.data
        
        # Xử lý trạng thái xuất bản
        was_published = article.is_published
        article.is_published = form.is_published.data
        
        if form.is_published.data and not was_published:
            article.published_at = datetime.utcnow()
        
        # Xử lý tags
        article.tags.clear()
        if form.tags.data:
            tag_names = [tag.strip() for tag in form.tags.data.split(',')]
            for tag_name in tag_names:
                if tag_name:
                    tag_slug = create_slug(tag_name)
                    tag = Tag.query.filter_by(slug=tag_slug).first()
                    if not tag:
                        tag = Tag(name=tag_name, slug=tag_slug)
                        db.session.add(tag)
                    article.tags.append(tag)
        
        article.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Đã cập nhật bài viết thành công!', 'success')
        return redirect(url_for('admin_articles'))
    
    return render_template('admin/edit_article.html', form=form, article=article)

@app.route('/admin/articles/<int:id>/delete', methods=['POST'])
@admin_required
def admin_delete_article(id):
    """Xóa bài viết"""
    article = Article.query.get_or_404(id)
    
    # Xóa các quan hệ
    article.tags.clear()
    
    db.session.delete(article)
    db.session.commit()
    
    flash('Đã xóa bài viết thành công!', 'success')
    return redirect(url_for('admin_articles'))

@app.route('/admin/categories')
@admin_required
def admin_categories():
    """Quản lý danh mục"""
    categories = Category.query.order_by(Category.sort_order, Category.name).all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['GET', 'POST'])
@admin_required
def admin_add_category():
    """Thêm danh mục mới"""
    form = CategoryForm()
    
    if form.validate_on_submit():
        slug = form.slug.data or create_slug(form.name.data)
        
        # Kiểm tra tên và slug trùng lặp
        if Category.query.filter_by(name=form.name.data).first():
            flash('Tên danh mục đã được sử dụng.', 'error')
            return render_template('admin/add_category.html', form=form)
        
        if Category.query.filter_by(slug=slug).first():
            flash('Slug URL đã được sử dụng.', 'error')
            return render_template('admin/add_category.html', form=form)
        
        category = Category(
            name=form.name.data,
            slug=slug,
            description=form.description.data,
            icon=form.icon.data,
            color=form.color.data or '#007bff',
            is_active=form.is_active.data,
            sort_order=int(form.sort_order.data) if form.sort_order.data else 0
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash('Đã thêm danh mục thành công!', 'success')
        return redirect(url_for('admin_categories'))
    
    return render_template('admin/add_category.html', form=form)

@app.route('/admin/users')
@admin_required
def admin_users():
    """Quản lý người dùng"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter theo trạng thái
    status = request.args.get('status', 'all')
    query = User.query
    
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    elif status == 'admin':
        query = query.filter_by(is_admin=True)
    elif status == 'editor':
        query = query.filter_by(is_editor=True)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/users.html', users=users, current_status=status)

@app.route('/admin/comments')
@admin_required
def admin_comments():
    """Quản lý bình luận"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Filter theo trạng thái
    status = request.args.get('status', 'all')
    query = Comment.query
    
    if status == 'approved':
        query = query.filter_by(is_approved=True)
    elif status == 'pending':
        query = query.filter_by(is_approved=False)
    elif status == 'hidden':
        query = query.filter_by(is_hidden=True)
    
    comments = query.order_by(Comment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/comments.html', comments=comments, current_status=status)

@app.route('/admin/comments/<int:id>/approve', methods=['POST'])
@admin_required
def admin_approve_comment(id):
    """Duyệt bình luận"""
    comment = Comment.query.get_or_404(id)
    comment.is_approved = True
    db.session.commit()
    
    flash('Đã duyệt bình luận thành công!', 'success')
    return redirect(request.referrer or url_for('admin_comments'))

@app.route('/admin/comments/<int:id>/hide', methods=['POST'])
@admin_required
def admin_hide_comment(id):
    """Ẩn bình luận"""
    comment = Comment.query.get_or_404(id)
    comment.is_hidden = True
    db.session.commit()
    
    flash('Đã ẩn bình luận thành công!', 'success')
    return redirect(request.referrer or url_for('admin_comments'))

@app.route('/admin/ads')
@admin_required
def admin_ads():
    """Quản lý quảng cáo"""
    ads = Advertisement.query.order_by(Advertisement.created_at.desc()).all()
    return render_template('admin/ads.html', ads=ads)

@app.route('/admin/ads/add', methods=['GET', 'POST'])
@admin_required
def admin_add_ad():
    """Thêm quảng cáo mới"""
    form = AdvertisementForm()
    
    if form.validate_on_submit():
        ad = Advertisement(
            title=form.title.data,
            content=form.content.data,
            link_url=form.link_url.data,
            position=form.position.data,
            is_active=form.is_active.data
        )
        
        db.session.add(ad)
        db.session.commit()
        
        flash('Đã thêm quảng cáo thành công!', 'success')
        return redirect(url_for('admin_ads'))
    
    return render_template('admin/add_ad.html', form=form)

# API endpoints cho admin
@app.route('/admin/api/stats')
@admin_required
def admin_api_stats():
    """API lấy thống kê cho dashboard"""
    # Thống kê lượt xem theo ngày (7 ngày gần nhất)
    daily_views = []
    for i in range(7):
        date = datetime.utcnow().date() - timedelta(days=i)
        # Giả sử có bảng page_views để track lượt xem
        # views = PageView.query.filter(func.date(PageView.created_at) == date).count()
        views = 100 + i * 20  # Mock data
        daily_views.append({
            'date': date.strftime('%d/%m'),
            'views': views
        })
    
    daily_views.reverse()
    
    return jsonify({
        'daily_views': daily_views
    })

@app.route('/admin/api/articles/<int:id>/toggle-featured', methods=['POST'])
@admin_required
def admin_toggle_featured(id):
    """Toggle trạng thái nổi bật của bài viết"""
    article = Article.query.get_or_404(id)
    article.is_featured = not article.is_featured
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_featured': article.is_featured
    })

@app.route('/admin/api/users/<int:id>/toggle-active', methods=['POST'])
@admin_required
def admin_toggle_user_active(id):
    """Toggle trạng thái kích hoạt người dùng"""
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Không thể khóa chính mình'})
    
    user.is_active = not user.is_active
    db.session.commit()
    
    return jsonify({
        'success': True,
        'is_active': user.is_active
    })
