from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, BooleanField, SelectField, FileField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from wtforms.widgets import TextArea
from flask_wtf.file import FileAllowed
from models import User, Category

class CKEditorWidget(TextArea):
    """Widget tùy chỉnh cho CKEditor"""
    def __call__(self, field, **kwargs):
        kwargs.setdefault('class_', 'ckeditor')
        return super(CKEditorWidget, self).__call__(field, **kwargs)

class CKEditorField(TextAreaField):
    """Field tùy chỉnh cho CKEditor"""
    widget = CKEditorWidget()

class LoginForm(FlaskForm):
    """Form đăng nhập"""
    username = StringField('Tên đăng nhập', validators=[
        DataRequired(message='Vui lòng nhập tên đăng nhập'),
        Length(min=3, max=80, message='Tên đăng nhập phải từ 3-80 ký tự')
    ])
    password = PasswordField('Mật khẩu', validators=[
        DataRequired(message='Vui lòng nhập mật khẩu')
    ])
    remember_me = BooleanField('Ghi nhớ đăng nhập')

class RegisterForm(FlaskForm):
    """Form đăng ký"""
    username = StringField('Tên đăng nhập', validators=[
        DataRequired(message='Vui lòng nhập tên đăng nhập'),
        Length(min=3, max=80, message='Tên đăng nhập phải từ 3-80 ký tự')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Vui lòng nhập email'),
        Email(message='Email không hợp lệ')
    ])
    full_name = StringField('Họ tên', validators=[
        DataRequired(message='Vui lòng nhập họ tên'),
        Length(min=2, max=100, message='Họ tên phải từ 2-100 ký tự')
    ])
    password = PasswordField('Mật khẩu', validators=[
        DataRequired(message='Vui lòng nhập mật khẩu'),
        Length(min=6, message='Mật khẩu phải ít nhất 6 ký tự')
    ])
    confirm_password = PasswordField('Xác nhận mật khẩu', validators=[
        DataRequired(message='Vui lòng xác nhận mật khẩu'),
        EqualTo('password', message='Mật khẩu xác nhận không khớp')
    ])
    
    def validate_username(self, username):
        """Kiểm tra tên đăng nhập đã tồn tại"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.')
    
    def validate_email(self, email):
        """Kiểm tra email đã tồn tại"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email đã được sử dụng. Vui lòng chọn email khác.')

class ProfileForm(FlaskForm):
    """Form cập nhật hồ sơ"""
    username = StringField('Tên đăng nhập', validators=[
        DataRequired(message='Vui lòng nhập tên đăng nhập'),
        Length(min=3, max=80, message='Tên đăng nhập phải từ 3-80 ký tự')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Vui lòng nhập email'),
        Email(message='Email không hợp lệ')
    ])
    full_name = StringField('Họ tên', validators=[
        Length(max=100, message='Họ tên không được quá 100 ký tự')
    ])
    bio = TextAreaField('Giới thiệu', validators=[
        Length(max=500, message='Giới thiệu không được quá 500 ký tự')
    ])
    avatar = FileField('Ảnh đại diện', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Chỉ cho phép file ảnh!')
    ])

class ArticleForm(FlaskForm):
    """Form tạo/chỉnh sửa bài viết"""
    title = StringField('Tiêu đề', validators=[
        DataRequired(message='Vui lòng nhập tiêu đề'),
        Length(min=5, max=200, message='Tiêu đề phải từ 5-200 ký tự')
    ])
    summary = TextAreaField('Tóm tắt', validators=[
        Length(max=500, message='Tóm tắt không được quá 500 ký tự')
    ])
    content = CKEditorField('Nội dung', validators=[
        DataRequired(message='Vui lòng nhập nội dung bài viết')
    ])
    category_id = SelectField('Danh mục', coerce=int, validators=[
        DataRequired(message='Vui lòng chọn danh mục')
    ])
    tags = StringField('Tags', validators=[
        Length(max=200, message='Tags không được quá 200 ký tự')
    ])
    featured_image = FileField('Ảnh đại diện', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Chỉ cho phép file ảnh!')
    ])
    is_published = BooleanField('Xuất bản ngay')
    is_featured = BooleanField('Bài viết nổi bật')
    
    def __init__(self, *args, **kwargs):
        super(ArticleForm, self).__init__(*args, **kwargs)
        # Lấy danh sách danh mục để hiển thị trong select
        self.category_id.choices = [(c.id, c.name) for c in Category.query.filter_by(is_active=True).all()]

class CommentForm(FlaskForm):
    """Form bình luận"""
    content = TextAreaField('Bình luận', validators=[
        DataRequired(message='Vui lòng nhập nội dung bình luận'),
        Length(min=5, max=1000, message='Bình luận phải từ 5-1000 ký tự')
    ])

class SearchForm(FlaskForm):
    """Form tìm kiếm"""
    query = StringField('Từ khóa', validators=[
        DataRequired(message='Vui lòng nhập từ khóa tìm kiếm'),
        Length(min=2, max=100, message='Từ khóa phải từ 2-100 ký tự')
    ])
    category = SelectField('Danh mục', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        # Thêm tùy chọn "Tất cả danh mục"
        self.category.choices = [(0, 'Tất cả danh mục')] + [(c.id, c.name) for c in Category.query.filter_by(is_active=True).all()]

class CategoryForm(FlaskForm):
    """Form tạo/chỉnh sửa danh mục"""
    name = StringField('Tên danh mục', validators=[
        DataRequired(message='Vui lòng nhập tên danh mục'),
        Length(min=2, max=50, message='Tên danh mục phải từ 2-50 ký tự')
    ])
    description = TextAreaField('Mô tả', validators=[
        Length(max=500, message='Mô tả không được quá 500 ký tự')
    ])
    icon = StringField('Icon CSS Class', validators=[
        Length(max=50, message='Icon class không được quá 50 ký tự')
    ])
    color = StringField('Màu sắc', validators=[
        Length(max=7, message='Mã màu không hợp lệ')
    ])
    is_active = BooleanField('Kích hoạt', default=True)

class AdvertisementForm(FlaskForm):
    """Form tạo/chỉnh sửa quảng cáo"""
    title = StringField('Tiêu đề', validators=[
        DataRequired(message='Vui lòng nhập tiêu đề'),
        Length(min=2, max=100, message='Tiêu đề phải từ 2-100 ký tự')
    ])
    content = TextAreaField('Nội dung', validators=[
        Length(max=1000, message='Nội dung không được quá 1000 ký tự')
    ])
    image_url = StringField('URL ảnh', validators=[
        Length(max=200, message='URL ảnh không được quá 200 ký tự')
    ])
    link_url = StringField('URL liên kết', validators=[
        Length(max=200, message='URL liên kết không được quá 200 ký tự')
    ])
    position = SelectField('Vị trí', choices=[
        ('header', 'Header'),
        ('sidebar', 'Sidebar'),
        ('footer', 'Footer'),
        ('inline', 'Trong bài viết')
    ], validators=[DataRequired(message='Vui lòng chọn vị trí')])
    is_active = BooleanField('Kích hoạt', default=True)
