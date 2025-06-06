import os
import secrets
from datetime import datetime, date
from PIL import Image
from flask import current_app, url_for
from werkzeug.utils import secure_filename
import re
from unidecode import unidecode

def slugify(text):
    """Chuyển đổi text thành slug URL-friendly"""
    if not text:
        return ""
    
    # Chuyển đổi từ tiếng Việt sang ASCII
    text = unidecode(text)
    
    # Chuyển thành lowercase và thay thế khoảng trắng bằng dấu gạch ngang
    text = re.sub(r'[^\w\s-]', '', text.lower().strip())
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    
    return text

def save_uploaded_file(form_file, folder='uploads'):
    """Lưu file upload và trả về tên file"""
    if not form_file:
        return None
    
    # Tạo tên file ngẫu nhiên để tránh trùng lặp
    random_hex = secrets.token_hex(8)
    _, file_ext = os.path.splitext(form_file.filename)
    filename = random_hex + file_ext
    
    # Đường dẫn lưu file
    upload_folder = os.path.join(current_app.root_path, 'static', folder)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    file_path = os.path.join(upload_folder, filename)
    
    # Resize ảnh nếu cần thiết
    if file_ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
        try:
            img = Image.open(form_file)
            
            # Resize ảnh nếu quá lớn (max 1200px width)
            if img.width > 1200:
                ratio = 1200 / img.width
                new_height = int(img.height * ratio)
                img = img.resize((1200, new_height), Image.Resampling.LANCZOS)
            
            img.save(file_path, optimize=True, quality=85)
        except Exception as e:
            current_app.logger.error(f"Lỗi khi xử lý ảnh: {e}")
            form_file.save(file_path)
    else:
        form_file.save(file_path)
    
    return filename

def format_datetime(dt, format='%d/%m/%Y %H:%M'):
    """Format datetime cho hiển thị"""
    if not dt:
        return ""
    return dt.strftime(format)

def format_date(dt, format='%d/%m/%Y'):
    """Format date cho hiển thị"""
    if not dt:
        return ""
    if isinstance(dt, datetime):
        return dt.date().strftime(format)
    return dt.strftime(format)

def time_ago(dt):
    """Hiển thị thời gian tương đối (vd: 2 giờ trước)"""
    if not dt:
        return ""
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 30:
        return format_date(dt)
    elif diff.days > 0:
        return f"{diff.days} ngày trước"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} giờ trước"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} phút trước"
    else:
        return "Vừa xong"

def truncate_text(text, max_length=150, suffix='...'):
    """Cắt ngắn text với suffix"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length].strip() + suffix

def allowed_file(filename, allowed_extensions=None):
    """Kiểm tra file có được phép upload không"""
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_url(filename, folder='uploads'):
    """Lấy URL đầy đủ của file"""
    if not filename:
        return None
    return url_for('static', filename=f'{folder}/{filename}')

def process_tags(tag_string):
    """Xử lý chuỗi tag thành list"""
    if not tag_string:
        return []
    
    # Tách tag bằng dấu phẩy và loại bỏ khoảng trắng
    tags = [tag.strip() for tag in tag_string.split(',') if tag.strip()]
    return tags

def generate_excerpt(content, max_length=200):
    """Tạo excerpt từ nội dung HTML"""
    # Loại bỏ HTML tags
    clean_text = re.sub(r'<[^>]+>', '', content)
    
    # Loại bỏ khoảng trắng thừa
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return truncate_text(clean_text, max_length)

def update_site_stats():
    """Cập nhật thống kê website hàng ngày"""
    from models import SiteStats, Article, Comment, User
    from app import db
    
    today = date.today()
    
    # Tìm hoặc tạo bản ghi thống kê cho ngày hôm nay
    stats = SiteStats.query.filter_by(date=today).first()
    if not stats:
        stats = SiteStats(date=today)
        db.session.add(stats)
    
    # Cập nhật số liệu
    stats.article_views = Article.query.with_entities(db.func.sum(Article.view_count)).scalar() or 0
    stats.comments_count = Comment.query.filter(
        db.func.date(Comment.created_at) == today
    ).count()
    stats.new_users = User.query.filter(
        db.func.date(User.created_at) == today
    ).count()
    
    db.session.commit()

def get_popular_tags(limit=10):
    """Lấy danh sách tag phổ biến"""
    from models import Tag, article_tags
    from app import db
    
    # Query để đếm số bài viết cho mỗi tag
    popular_tags = db.session.query(Tag, db.func.count(article_tags.c.article_id).label('count'))\
        .join(article_tags)\
        .group_by(Tag.id)\
        .order_by(db.func.count(article_tags.c.article_id).desc())\
        .limit(limit)\
        .all()
    
    return popular_tags

def get_recent_articles(limit=5, exclude_id=None):
    """Lấy danh sách bài viết gần đây"""
    from models import Article
    
    query = Article.query.filter_by(is_published=True)
    
    if exclude_id:
        query = query.filter(Article.id != exclude_id)
    
    return query.order_by(Article.published_at.desc()).limit(limit).all()

def get_featured_articles(limit=3):
    """Lấy danh sách bài viết nổi bật"""
    from models import Article
    
    return Article.query.filter_by(is_published=True, is_featured=True)\
        .order_by(Article.published_at.desc())\
        .limit(limit)\
        .all()

def search_articles(query, category_id=None, page=1, per_page=10):
    """Tìm kiếm bài viết"""
    from models import Article
    
    # Tạo query cơ bản
    articles = Article.query.filter_by(is_published=True)
    
    # Thêm điều kiện tìm kiếm
    if query:
        search_filter = db.or_(
            Article.title.ilike(f'%{query}%'),
            Article.summary.ilike(f'%{query}%'),
            Article.content.ilike(f'%{query}%')
        )
        articles = articles.filter(search_filter)
    
    # Lọc theo danh mục
    if category_id and category_id > 0:
        articles = articles.filter_by(category_id=category_id)
    
    # Sắp xếp và phân trang
    return articles.order_by(Article.published_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
