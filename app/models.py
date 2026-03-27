from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def set_password(self, password):
        """使用 SHA256 加密密码"""
        self.password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def check_password(self, password):
        """验证密码"""
        return self.password_hash == hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def is_locked(self):
        """检查账号是否被锁定"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def increment_login_attempts(self, max_attempts, lockout_minutes):
        """增加登录失败次数"""
        self.login_attempts += 1
        if self.login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
        db.session.commit()
    
    def reset_login_attempts(self):
        """重置登录失败次数"""
        self.login_attempts = 0
        self.locked_until = None
        db.session.commit()
    
    @staticmethod
    def validate_password_strength(password):
        """验证密码强度：至少8位，包含字母和数字"""
        if len(password) < 8:
            return False, "密码长度至少8位"
        if not any(char.isalpha() for char in password):
            return False, "密码必须包含字母"
        if not any(char.isdigit() for char in password):
            return False, "密码必须包含数字"
        return True, ""
    
    def __repr__(self):
        return f'<User {self.username}>'

class VerificationCode(db.Model):
    """验证码模型"""
    __tablename__ = 'verification_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    contact = db.Column(db.String(120), nullable=False, index=True)  # 手机号或邮箱
    code = db.Column(db.String(10), nullable=False)
    code_type = db.Column(db.String(20), nullable=False)  # register, login, reset_password
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    
    def is_valid(self):
        """检查验证码是否有效"""
        return not self.used and self.expires_at > datetime.utcnow()
    
    def mark_as_used(self):
        """标记验证码为已使用"""
        self.used = True
        db.session.commit()
    
    @staticmethod
    def generate_code(contact, code_type, expire_minutes=5):
        """生成验证码"""
        import random
        code = str(random.randint(100000, 999999))
        expires_at = datetime.utcnow() + timedelta(minutes=expire_minutes)
        
        # 删除该联系人的旧验证码
        VerificationCode.query.filter_by(
            contact=contact,
            code_type=code_type,
            used=False
        ).delete()
        
        verification_code = VerificationCode(
            contact=contact,
            code=code,
            code_type=code_type,
            expires_at=expires_at
        )
        db.session.add(verification_code)
        db.session.commit()
        return code
    
    @staticmethod
    def verify_code(contact, code, code_type):
        """验证验证码"""
        verification_code = VerificationCode.query.filter_by(
            contact=contact,
            code=code,
            code_type=code_type
        ).first()
        
        if not verification_code or not verification_code.is_valid():
            return False
        
        verification_code.mark_as_used()
        return True


class GarbageCategory(db.Model):
    """垃圾分类模型"""
    __tablename__ = 'garbage_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<GarbageCategory {self.name}>'


class Feedback(db.Model):
    """反馈信息模型"""
    __tablename__ = 'feedbacks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    garbage_name = db.Column(db.String(100), nullable=False)
    wrong_category_id = db.Column(db.Integer, db.ForeignKey('garbage_categories.id'), nullable=False)
    correct_category_id = db.Column(db.Integer, db.ForeignKey('garbage_categories.id'), nullable=False)
    status = db.Column(db.Enum('pending', 'processed', 'ignored'), default='pending', nullable=False, index=True)
    image_path = db.Column(db.String(255))
    note = db.Column(db.Text)
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 关联关系
    user = db.relationship('User', backref=db.backref('feedbacks', lazy=True))
    wrong_category = db.relationship('GarbageCategory', foreign_keys=[wrong_category_id], backref=db.backref('wrong_feedbacks', lazy=True))
    correct_category = db.relationship('GarbageCategory', foreign_keys=[correct_category_id], backref=db.backref('correct_feedbacks', lazy=True))
    
    def __repr__(self):
        return f'<Feedback {self.id} - {self.garbage_name}>'
