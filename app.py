import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Cấu hình logging để debug dễ dàng hơn
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Khởi tạo extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    """Factory function để tạo Flask app"""
    app = Flask(__name__)
    
    # Cấu hình bảo mật
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Cấu hình database PostgreSQL
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:password@localhost:5432/sports_news"
    )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Cấu hình Flask-Login
    app.config["LOGIN_VIEW"] = "auth.login"
    app.config["LOGIN_MESSAGE"] = "Vui lòng đăng nhập để truy cập trang này."
    app.config["LOGIN_MESSAGE_CATEGORY"] = "info"
    
    # Khởi tạo extensions với app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # User loader cho Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))
    
    # Tạo bảng database
    with app.app_context():
        # Import models để SQLAlchemy biết về các bảng
        import models
        db.create_all()
        logging.info("Đã tạo tất cả bảng database")
    
    # Đăng ký blueprints/routes
    from routes import main_bp, auth_bp, admin_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app

# Tạo app instance
app = create_app()
