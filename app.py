import os
import logging
from flask import Flask, current_app 
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

from apscheduler.schedulers.background import BackgroundScheduler
import atexit 

from flask_migrate import Migrate # Đảm bảo import Flask-Migrate

logging.basicConfig(level=logging.INFO) 

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
csrf = CSRFProtect()

migrate = Migrate() # Khởi tạo Migrate

scheduler = BackgroundScheduler()

def create_app():
    app = Flask(__name__)
    
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # THAY ĐỔI QUAN TRỌNG: Sửa tên database thành 'webtintuc_db'
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", 
        "postgresql://sportspulse_user:11032005@localhost:5432/webtintuc_db" # <-- Đã sửa tên database!
    )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    app.config["LOGIN_VIEW"] = "auth.login"
    app.config["LOGIN_MESSAGE"] = "Vui lòng đăng nhập để truy cập trang này."
    app.config["LOGIN_MESSAGE_CATEGORY"] = "info"
    
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db) # Khởi tạo Migrate với app và db
    
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))
    
    # LƯU Ý: db.create_all() sẽ cố gắng tạo lại bảng.
    # Khi dùng Flask-Migrate, bạn nên tin tưởng vào 'flask db upgrade' để quản lý schema.
    # Tùy thuộc vào việc 'webtintuc_db' đã có các bảng của bạn chưa, dòng này có thể gây lỗi.
    # Tốt nhất là bỏ comment dòng này sau khi bạn đã chạy 'flask db upgrade' thành công trên database này.
    with app.app_context():
        import models
        # db.create_all() # <-- Có thể tạm thời bỏ comment hoặc xóa nếu bạn đã có bảng từ migrate
        logging.info("Đã tạo tất cả bảng database") # Dòng log này vẫn có thể xuất hiện dù không tạo lại

        # ... (Phần Scheduler của bạn)
        from utils import fetch_and_save_news
        
        def job_function():
            with app.app_context():
                fetch_and_save_news()
                
        if not scheduler.running:
            app.logger.info("Đang chạy fetch_and_save_news lần đầu (tức thì)...")
            job_function() 
            
            scheduler.add_job(func=job_function, trigger="interval", minutes=60, id='news_fetch_job', replace_existing=True)
            scheduler.start()
            app.logger.info("Scheduler đã được khởi động để cập nhật tin tức mỗi 60 phút.") 

    from routes import main_bp, auth_bp, admin_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app

app = create_app()

atexit.register(lambda: scheduler.shutdown())