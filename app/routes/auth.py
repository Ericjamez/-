from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from email_validator import validate_email, EmailNotValidError
from datetime import datetime
import re
from app.models import db, User, VerificationCode
from app.utils import send_email

auth_bp = Blueprint('auth', __name__)

# ==================== 工具函数 ====================

def validate_phone(phone):
    """验证手机号格式"""
    pattern = r'^1[3-9]\d{9}$'
    return re.match(pattern, phone) is not None

def generate_captcha():
    """生成图形验证码（简化版，实际项目应使用 PIL 或其他库生成图片）"""
    import random
    import string
    captcha = ''.join(random.choices(string.digits, k=4))
    session['captcha'] = captcha
    return captcha

def verify_captcha(captcha_input):
    """验证图形验证码"""
    return session.get('captcha') == captcha_input

@auth_bp.route('/generate-captcha')
def generate_captcha_route():
    """生成图形验证码"""
    captcha = generate_captcha()
    return jsonify({'success': True, 'captcha': captcha})

# ==================== 路由：F001 用户注册 ====================

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页面"""
    if request.method == 'POST':
        # 获取表单数据
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        contact_type = request.form.get('contact_type', 'phone')  # phone 或 email
        contact = phone if contact_type == 'phone' else email
        verification_code = request.form.get('verification_code', '').strip()
        
        # 错误信息字典，按字段分类
        field_errors = {
            'username': [],
            'password': [],
            'confirm_password': [],
            'contact': [],
            'verification_code': []
        }
        
        # 1. 验证用户名
        if not username:
            field_errors['username'].append('用户名不能为空')
        elif len(username) < 3 or len(username) > 20:
            field_errors['username'].append('用户名长度应为3-20个字符')
        elif User.query.filter_by(username=username).first():
            field_errors['username'].append('用户名已存在')
        
        # 2. 验证密码
        if not password:
            field_errors['password'].append('密码不能为空')
        else:
            is_valid, msg = User.validate_password_strength(password)
            if not is_valid:
                field_errors['password'].append(msg)
        
        if password != confirm_password:
            field_errors['confirm_password'].append('两次密码输入不一致')
        
        # 3. 验证邮箱
        if not contact:
            field_errors['contact'].append('请填写邮箱')
        else:
            try:
                validate_email(email)
                if User.query.filter_by(email=email).first():
                    field_errors['contact'].append('该邮箱已注册')
            except EmailNotValidError:
                field_errors['contact'].append('邮箱格式不正确')
        
        # 4. 验证验证码
        if not verification_code:
            field_errors['verification_code'].append('请输入验证码')
        elif not VerificationCode.verify_code(contact, verification_code, 'register'):
            field_errors['verification_code'].append('验证码错误或已过期')
        
        # 检查是否有错误
        has_errors = any(errors for errors in field_errors.values())
        if has_errors:
            return render_template('register.html', 
                                   username=username, 
                                   phone=phone, 
                                   email=email,
                                   password=password,
                                   confirm_password=confirm_password,
                                   verification_code=verification_code,
                                   contact_type=contact_type,
                                   field_errors=field_errors)
        
        # 创建用户
        user = User(
            username=username,
            phone=phone if contact_type == 'phone' else None,
            email=email if contact_type == 'email' else None
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('注册成功！请登录', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('注册失败，请稍后重试', 'error')
    
    return render_template('register.html')

@auth_bp.route('/send-verification-code', methods=['POST'])
def send_verification_code():
    """发送验证码"""
    contact = request.form.get('contact', '').strip()
    code_type = request.form.get('code_type', 'register')
    
    if not contact:
        return jsonify({'success': False, 'message': '请填写邮箱'})
    
    # 验证邮箱格式
    try:
        validate_email(contact)
    except EmailNotValidError:
        return jsonify({'success': False, 'message': '邮箱格式不正确'})
    
    # 检查是否已注册（注册时）
    if code_type == 'register':
        if User.query.filter_by(email=contact).first():
            return jsonify({'success': False, 'message': '该邮箱已注册'})
    elif code_type in ['login', 'reset_password']:
        if not User.query.filter_by(email=contact).first():
            return jsonify({'success': False, 'message': '该邮箱未注册'})
    
    # 生成验证码
    code = VerificationCode.generate_code(contact, code_type)
    
    # 发送邮箱验证码
    success, message = send_email(contact, code)
    if success:
        return jsonify({
            'success': True, 
            'message': f'验证码已发送到 {contact}'
        })
    else:
        return jsonify({
            'success': False, 
            'message': f'发送失败：{message}'
        })

# ==================== 路由：F002 用户登录 ====================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """普通用户登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        captcha = request.form.get('captcha', '').strip()
        
        # 错误信息字典，按字段分类
        field_errors = {
            'username': [],
            'password': [],
            'captcha': []
        }
        
        if not username:
            field_errors['username'].append('请输入用户名')
        
        if not password:
            field_errors['password'].append('请输入密码')
        
        if not captcha:
            field_errors['captcha'].append('请输入验证码')
        elif not verify_captcha(captcha):
            field_errors['captcha'].append('验证码错误')
        
        # 检查是否有错误
        has_errors = any(errors for errors in field_errors.values())
        if has_errors:
            return render_template('login.html', 
                                   username=username,
                                   field_errors=field_errors)
        
        # 查找用户
        user = User.query.filter_by(username=username, is_admin=False).first()
        
        # 检查是否锁定
        if user and user.is_locked():
            remaining_minutes = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            field_errors['username'].append(f'账号已锁定，请 {remaining_minutes} 分钟后再试')
        # 验证密码
        elif user and user.check_password(password):
            # 登录成功，重置失败次数
            user.reset_login_attempts()
            session['user_id'] = user.id
            session['username'] = user.username
            flash('登录成功！', 'success')
            return redirect(url_for('auth.index'))
        else:
            # 用户名或密码错误
            field_errors['password'].append('用户名或密码错误')
            # 增加登录失败次数
            if user:
                user.increment_login_attempts(5, 10)
                remaining_attempts = 5 - user.login_attempts
                if remaining_attempts <= 0:
                    field_errors['password'].append('密码错误次数过多，账号已被锁定10分钟')
        
        # 检查是否有错误
        has_errors = any(errors for errors in field_errors.values())
        if has_errors:
            return render_template('login.html', 
                                   username=username,
                                   field_errors=field_errors)
    
    return render_template('login.html')

# ==================== 路由：F003 管理员登录 ====================

@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # 错误信息字典，按字段分类
        field_errors = {
            'username': [],
            'password': []
        }
        
        if not username:
            field_errors['username'].append('请输入管理员账号')
        
        if not password:
            field_errors['password'].append('请输入密码')
        
        # 查找管理员
        admin = User.query.filter_by(username=username, is_admin=True).first()
        
        # 检查是否锁定
        if admin and admin.is_locked():
            remaining_minutes = int((admin.locked_until - datetime.utcnow()).total_seconds() / 60)
            field_errors['username'].append(f'账号已锁定，请 {remaining_minutes} 分钟后再试')
        # 验证密码
        elif admin and admin.check_password(password):
            # 登录成功，重置失败次数
            admin.reset_login_attempts()
            session['user_id'] = admin.id
            session['username'] = admin.username
            session['is_admin'] = True
            flash('管理员登录成功！', 'success')
            return redirect(url_for('auth.admin_dashboard'))
        elif admin:
            # 密码错误
            field_errors['password'].append('密码错误')
            admin.increment_login_attempts(5, 10)
            remaining_attempts = 5 - admin.login_attempts
            if remaining_attempts <= 0:
                field_errors['password'].append('密码错误次数过多，账号已被锁定10分钟')
        elif username:
            # 管理员账号不存在
            field_errors['username'].append('管理员账号不存在')
        
        # 检查是否有错误
        has_errors = any(errors for errors in field_errors.values())
        if has_errors:
            return render_template('admin_login.html', 
                                   username=username,
                                   field_errors=field_errors)
    
    return render_template('admin_login.html')

# ==================== 路由：F004 密码找回 ====================

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """密码找回"""
    if request.method == 'POST':
        contact = request.form.get('contact', '').strip()
        verification_code = request.form.get('verification_code', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # 错误信息字典，按字段分类
        field_errors = {
            'contact': [],
            'verification_code': [],
            'new_password': [],
            'confirm_password': []
        }
        
        # 验证邮箱
        if not contact:
            field_errors['contact'].append('请输入邮箱')
        else:
            try:
                validate_email(contact)
                # 查找用户
                user = User.query.filter_by(email=contact, is_admin=False).first()
                if not user:
                    field_errors['contact'].append('该账号未注册或为管理员账号（管理员无法自主找回密码）')
            except EmailNotValidError:
                field_errors['contact'].append('邮箱格式不正确')
        
        # 验证验证码
        if not verification_code:
            field_errors['verification_code'].append('请输入验证码')
        elif not VerificationCode.verify_code(contact, verification_code, 'reset_password'):
            field_errors['verification_code'].append('验证码错误或已过期')
        
        # 验证新密码
        if not new_password:
            field_errors['new_password'].append('请输入新密码')
        else:
            is_valid, msg = User.validate_password_strength(new_password)
            if not is_valid:
                field_errors['new_password'].append(msg)
        
        if new_password != confirm_password:
            field_errors['confirm_password'].append('两次密码输入不一致')
        
        # 检查是否有错误
        has_errors = any(errors for errors in field_errors.values())
        if has_errors:
            return render_template('forgot_password.html', 
                                   contact=contact,
                                   field_errors=field_errors)
        
        # 重置密码
        user.set_password(new_password)
        user.reset_login_attempts()  # 重置失败次数
        db.session.commit()
        
        # 密码重置成功，显示成功消息
        return render_template('forgot_password.html', 
                               contact=contact,
                               success_message='密码重置成功！请使用新密码登录')
    
    return render_template('forgot_password.html')

# ==================== 首页和仪表盘 ====================

@auth_bp.route('/')
def index():
    """首页"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('index.html')

@auth_bp.route('/dashboard')
def dashboard():
    """用户仪表盘"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('dashboard.html')

@auth_bp.route('/recognition')
def recognition():
    """AI识别交互中心"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('recognition.html')

@auth_bp.route('/knowledge')
def knowledge():
    """垃圾分类知识图谱"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('knowledge.html')

@auth_bp.route('/analytics')
def analytics():
    """模型性能与统计"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('analytics.html')

@auth_bp.route('/feedback')
def feedback():
    """反馈与主动学习工作台"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('feedback.html')

@auth_bp.route('/deployment')
def deployment():
    """MindSpace部署实验化实验室"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('deployment.html')

@auth_bp.route('/admin/dashboard')
def admin_dashboard():
    """管理员仪表盘"""
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth.admin_login'))
    
    admin = User.query.get(session['user_id'])
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin_dashboard.html', admin=admin, users=users)

@auth_bp.route('/recognize', methods=['POST'])
def recognize():
    """识别垃圾图片"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '请上传图片'})
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({'success': False, 'message': '请选择图片'})
    
    # 保存图片到临时文件
    import os
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
        image.save(temp_file)
        temp_file_path = temp_file.name
    
    try:
        # 调用识别函数
        from app.utils import recognize_image
        success, result, confidence = recognize_image(temp_file_path)
        
        if success:
            # 生成知识内容
            knowledge = generate_knowledge(result)
            return jsonify({
                'success': True,
                'result': {
                    'category': result,
                    'confidence': confidence,
                    'time': round(0.1, 2)  # 模拟识别时间
                },
                'knowledge': knowledge
            })
        else:
            return jsonify({'success': False, 'message': result})
    finally:
        # 删除临时文件
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

def generate_knowledge(category):
    """根据分类生成知识内容"""
    knowledge_map = {
        '可回收物': '可回收物是指适宜回收利用和资源化利用的生活废弃物，如纸类、塑料、玻璃、金属和布料等。这些废弃物可以通过回收再利用，减少对环境的污染，节约资源。',
        '厨余垃圾': '厨余垃圾是指居民日常生活及食品加工、饮食服务、单位供餐等活动中产生的垃圾，包括丢弃不用的菜叶、剩菜、剩饭、果皮、蛋壳、茶渣、骨头等。这些垃圾可以通过堆肥等方式进行资源化利用。',
        '有害垃圾': '有害垃圾是指对人体健康或者自然环境造成直接或者潜在危害的生活废弃物，如废电池、废荧光灯管、废药品、废油漆及其容器等。这些垃圾需要特殊安全处理，避免对环境和人体健康造成危害。',
        '其他垃圾': '其他垃圾是指除可回收物、厨余垃圾、有害垃圾之外的其他生活废弃物，如砖瓦陶瓷、渣土、卫生间废纸、纸巾等难以回收的废弃物。这些垃圾通常采用焚烧或填埋的方式处理。'
    }
    return knowledge_map.get(category, '暂无相关知识')

@auth_bp.route('/feedback', methods=['POST'])
def feedback():
    """提交反馈"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    real_category = request.form.get('real_category', '').strip()
    note = request.form.get('note', '').strip()
    
    if not real_category:
        return jsonify({'success': False, 'message': '请选择真实的垃圾分类'})
    
    # 处理图片（如果有）
    if 'image' in request.files:
        image = request.files['image']
        if image.filename != '':
            # 这里可以添加保存图片的逻辑
            pass
    
    # 这里可以添加反馈数据的处理逻辑，例如保存到数据库
    
    return jsonify({'success': True, 'message': '反馈提交成功，感谢您的帮助！'})

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """登出"""
    session.clear()
    flash('已成功登出', 'success')
    return redirect(url_for('auth.login'))


