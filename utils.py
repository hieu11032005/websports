import os
import secrets
from datetime import datetime, date, timedelta
from PIL import Image
from flask import current_app, url_for
from werkzeug.utils import secure_filename
import re
from unidecode import unidecode
import logging

import requests
from bs4 import BeautifulSoup
# from trafilatura import extract # Không dùng trafilatura ở đây, dùng BeautifulSoup chi tiết hơn
from app import db
from models import Article, Category, Tag, User

logging.basicConfig(level=logging.INFO) # Đặt logging ở đây hoặc trong app.py

def slugify(text):
    """Chuyển đổi text thành slug URL-friendly"""
    if not text:
        return ""
    text = unidecode(text)
    text = re.sub(r'[^\w\s-]', '', text.lower().strip())
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text

def save_uploaded_file(form_file, folder='uploads'):
    """Lưu file upload và trả về tên file"""
    if not form_file:
        return None
    random_hex = secrets.token_hex(8)
    _, file_ext = os.path.splitext(form_file.filename)
    filename = random_hex + file_ext
    upload_folder = os.path.join(current_app.root_path, 'static', folder)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)
    if file_ext.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
        try:
            img = Image.open(form_file)
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
    tags = [tag.strip() for tag in tag_string.split(',') if tag.strip()]
    return tags

def generate_excerpt(content, max_length=200):
    """Tạo excerpt từ nội dung HTML"""
    # Loại bỏ các thẻ HTML để lấy văn bản thuần túy
    clean_text = re.sub(r'<[^>]+>', '', content)
    # Loại bỏ nhiều khoảng trắng liên tiếp
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return truncate_text(clean_text, max_length)

def update_site_stats():
    """Cập nhật thống kê website hàng ngày"""
    # Import lại để tránh circular import khi các hàm này gọi lẫn nhau
    from models import SiteStats, Article, Comment, User
    today = date.today()
    stats = SiteStats.query.filter_by(date=today).first()
    if not stats:
        stats = SiteStats(date=today)
        db.session.add(stats)

    stats.article_views = Article.query.with_entities(db.func.sum(Article.views_count)).scalar() or 0
    stats.comments_count = Comment.query.filter(
        db.func.date(Comment.created_at) == today
    ).count()
    stats.new_users = User.query.filter(
        db.func.date(User.created_at) == today
    ).count()

    db.session.commit()

def get_popular_tags(limit=10):
    """Lấy danh sách tag phổ biến"""
    from models import Tag, article_tags # Import lại để tránh circular import
    popular_tags = db.session.query(Tag, db.func.count(article_tags.c.article_id).label('count'))\
        .join(article_tags)\
        .group_by(Tag.id)\
        .order_by(db.func.count(article_tags.c.article_id).desc())\
        .limit(limit)\
        .all()
    return popular_tags

def get_recent_articles(limit=5, exclude_id=None):
    """Lấy danh sách bài viết gần đây"""
    from models import Article # Import lại để tránh circular import
    query = Article.query.filter_by(is_published=True)
    if exclude_id:
        query = query.filter(Article.id != exclude_id)
    return query.order_by(Article.published_at.desc()).limit(limit).all()

def get_featured_articles(limit=3):
    """Lấy danh sách bài viết nổi bật"""
    from models import Article # Import lại để tránh circular import
    return Article.query.filter_by(is_published=True, is_featured=True)\
        .order_by(Article.published_at.desc())\
        .limit(limit)\
        .all()

def search_articles(query, category_id=None, page=1, per_page=10):
    """Tìm kiếm bài viết"""
    from models import Article # Import lại để tránh circular import
    from sqlalchemy import or_
    articles = Article.query.filter_by(is_published=True)
    if query:
        search_filter = or_(
            Article.title.ilike(f'%{query}%'),
            Article.summary.ilike(f'%{query}%'),
            Article.content.ilike(f'%{query}%')
        )
        articles = articles.filter(search_filter)
    if category_id and category_id > 0:
        articles = articles.filter_by(category_id=category_id)
    return articles.order_by(Article.published_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

def scrape_single_article_details(article_url):
    """
    Hàm này truy cập một URL bài báo cụ thể và trích xuất nội dung đầy đủ,
    tiêu đề, tóm tắt và hình ảnh nổi bật.
    Điều chỉnh selector CSS/class phù hợp với trang web bạn muốn cạo (ở đây là VnExpress).
    """
    current_app.logger.info(f"Đang cạo chi tiết bài viết từ: {article_url}")
    try:
        response = requests.get(article_url, timeout=15)
        response.raise_for_status() # Kiểm tra lỗi HTTP (4xx, 5xx)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Tiêu đề
        title_tag = soup.find('h1', class_='title-detail')
        title = title_tag.get_text(strip=True) if title_tag else "Tiêu đề không tìm thấy"

        # 2. Tóm tắt/Mô tả (lead)
        description_tag = soup.find('p', class_='description')
        description = description_tag.get_text(strip=True) if description_tag else ""
        if not description and title_tag:
            # Fallback: cố gắng lấy vài câu đầu của nội dung nếu không có description riêng
            content_start = soup.find('article', class_='fck_detail')
            if content_start:
                first_p = content_start.find('p')
                if first_p:
                    description = truncate_text(first_p.get_text(strip=True), 200)

        # 3. Nội dung chính HTML (quan trọng nhất)
        article_body_tag = soup.find('article', class_='fck_detail')
        full_content_html = ""
        if article_body_tag:
            # Lấy toàn bộ HTML bên trong thẻ này để giữ nguyên định dạng
            full_content_html = str(article_body_tag)
            # Tùy chọn: Loại bỏ các thẻ không mong muốn hoặc quảng cáo nhúng nếu có
            # Ví dụ: for script in article_body_tag.find_all('script'): script.decompose()
            # for div_ad in article_body_tag.find_all('div', class_='my-ad-class'): div_ad.decompose()
        else:
            current_app.logger.warning(f"Không tìm thấy phần nội dung chính (article.fck_detail) cho URL: {article_url}")

        # 4. Hình ảnh nổi bật (featured_image)
        # Ưu tiên og:image hoặc meta description image
        featured_image_url = None
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            featured_image_url = og_image['content']
        else:
            # Fallback: tìm img trong body nếu có thể
            img_in_body = article_body_tag.find('img') if article_body_tag else None
            if img_in_body:
                featured_image_url = img_in_body.get('data-src') or img_in_body.get('src')

        # 5. Thời gian xuất bản
        published_date = datetime.utcnow() # Giá trị mặc định
        published_time_meta = soup.find('meta', property='article:published_time')
        if published_time_meta and published_time_meta.get('content'):
            try:
                # Chuyển đổi chuỗi ISO 8601 sang datetime object
                # Ví dụ: "2023-10-27T10:00:00+07:00"
                # Cần xử lý múi giờ hoặc bỏ qua múi giờ để lưu UTC
                dt_string = published_time_meta['content']
                # Xử lý múi giờ: bỏ phần múi giờ đi để parse dạng isoformat
                if '+' in dt_string:
                    dt_string = dt_string.split('+')[0]
                elif '-' in dt_string and dt_string.count('-') > 2: # Nếu có múi giờ dạng -HH:MM
                     dt_string = dt_string.rsplit('-', 1)[0]
                published_date = datetime.fromisoformat(dt_string)
                # Đảm bảo nó là naive datetime (không có múi giờ) và giả định là UTC
                published_date = published_date.replace(tzinfo=None)
            except ValueError as ve:
                current_app.logger.warning(f"Không thể parse published_time '{published_time_meta['content']}': {ve}. Dùng UTC hiện tại.")


        return {
            'title': title,
            'description': description, # Sẽ lưu vào trường `summary` của model Article
            'full_content_html': full_content_html, # Sẽ lưu vào trường `content` của model Article
            'source_url': article_url,
            'featured_image': featured_image_url,
            'published_at': published_date
        }
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Lỗi khi tải bài viết từ {article_url}: {e}")
        return None
    except Exception as e:
        current_app.logger.error(f"Lỗi không xác định khi phân tích cú pháp bài viết từ {article_url}: {e}", exc_info=True)
        return None

# Hàm chính để lấy tin tức từ nguồn và lưu vào database
def fetch_and_save_news():
    """
    Lấy tin tức thể thao từ một trang web mẫu (VnExpress Thể thao) và lưu vào database.
    Hàm này bây giờ sẽ cạo cả nội dung đầy đủ cho từng bài viết.
    """
    current_app.logger.info("Bắt đầu lấy và cập nhật tin tức...")

    SOURCE_CATEGORY_URL = "https://vnexpress.net/the-thao"

    try:
        response = requests.get(SOURCE_CATEGORY_URL, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        # Tìm các khối bài viết trên trang danh mục
        # VnExpress: 'item-news' thường là các bài viết chính
        # Hoặc tìm các thẻ 'article' hoặc 'div' chứa link đến bài viết
        articles_on_page = soup.find_all('article', class_='item-news')

        # Hoặc nếu cấu trúc khác:
        # articles_on_page = soup.select('.list_news .title_news a') # ví dụ cho link trong danh sách

        new_articles_count = 0

        # Tìm hoặc tạo user admin mặc định nếu chưa có
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', email='admin@example.com', full_name='Quản trị viên', is_admin=True, is_active=True)
            admin_user.set_password('adminpassword') # Đặt mật khẩu mặc định an toàn hơn
            db.session.add(admin_user)
            db.session.commit()
            current_app.logger.info("Đã tạo user admin mặc định: admin/adminpassword")

        # Tìm hoặc tạo category 'Thể thao'
        sports_category = Category.query.filter_by(name='Thể thao').first()
        if not sports_category:
            sports_category = Category(name='Thể thao', slug='the-thao', description='Tin tức thể thao tổng hợp', is_active=True, color='#007bff')
            db.session.add(sports_category)
            db.session.commit()
            current_app.logger.info("Đã tạo category 'Thể thao'.")

        for article_tag in articles_on_page:
            title_link_tag = article_tag.find('h3', class_='title-news')
            if not title_link_tag or not title_link_tag.a:
                continue # Bỏ qua nếu không tìm thấy tiêu đề hoặc link

            article_title = title_link_tag.a.text.strip()
            article_source_url = title_link_tag.a['href']

            # Quan trọng: Kiểm tra sự tồn tại bằng source_url
            existing_article = Article.query.filter_by(source_url=article_source_url).first()
            if existing_article:
                current_app.logger.info(f"Bài viết đã tồn tại (source_url): {article_title}")
                continue # Bỏ qua nếu đã có

            # Cạo nội dung chi tiết từ URL bài báo riêng
            article_details = scrape_single_article_details(article_source_url)

            if article_details and article_details['full_content_html']:
                # Tạo slug an toàn và duy nhất
                base_slug = slugify(article_details['title'])
                final_slug = base_slug
                counter = 1
                while Article.query.filter_by(slug=final_slug).first():
                    final_slug = f"{base_slug}-{counter}"
                    counter += 1

                new_article = Article(
                    title=article_details['title'],
                    slug=final_slug,
                    summary=article_details['description'],
                    content=article_details['full_content_html'], # Nội dung HTML đầy đủ
                    source_url=article_details['source_url'], # URL gốc
                    featured_image=article_details['featured_image'],
                    is_published=True, # Đặt là True để hiển thị ngay
                    published_at=article_details['published_at'],
                    author_id=admin_user.id,
                    category_id=sports_category.id
                )
                db.session.add(new_article)
                new_articles_count += 1
                current_app.logger.info(f"Đã thêm bài viết mới: {new_article.title}")
            else:
                current_app.logger.warning(f"Không thể cạo chi tiết hoặc nội dung trống cho URL: {article_source_url}")

        db.session.commit()
        current_app.logger.info(f"Kết thúc quá trình lấy tin tức. Đã thêm/cập nhật tổng cộng {new_articles_count} bài viết mới.")

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Lỗi khi yêu cầu URL nguồn danh mục ({SOURCE_CATEGORY_URL}): {e}")
    except Exception as e:
        current_app.logger.error(f"Lỗi không xác định khi fetch tin tức tổng hợp: {e}", exc_info=True)