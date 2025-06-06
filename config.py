import os

class Config:
    """Lớp cấu hình cơ bản"""
    SECRET_KEY = os.environ.get('SESSION_SECRET') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:password@localhost:5432/sports_news'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 300,
        'pool_pre_ping': True,
    }
    
    # Cấu hình phân trang
    POSTS_PER_PAGE = 12
    COMMENTS_PER_PAGE = 10
    
    # Cấu hình upload file
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

class DevelopmentConfig(Config):
    """Cấu hình cho môi trường development"""
    DEBUG = True

class ProductionConfig(Config):
    """Cấu hình cho môi trường production"""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
