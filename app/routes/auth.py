from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta
import re
from app.models import db, User, VerificationCode, Feedback, GarbageCategory, get_china_time
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
        
        field_errors = {
            'username': [],
            'password': [],
            'captcha': []
        }
        
        if not username:
            field_errors['username'].append('请输入用户名或邮箱')
        
        if not password:
            field_errors['password'].append('请输入密码')
        
        if not captcha:
            field_errors['captcha'].append('请输入验证码')
        elif not verify_captcha(captcha):
            field_errors['captcha'].append('验证码错误')
        
        has_errors = any(errors for errors in field_errors.values())
        if has_errors:
            return render_template('login.html', 
                                   username=username,
                                   field_errors=field_errors)
        
        user = User.query.filter(
            db.or_(
                User.username == username,
                User.email == username
            ),
            User.is_admin == False
        ).first()
        
        if user and user.is_locked():
            remaining_minutes = int((user.locked_until - get_china_time()).total_seconds() / 60)
            field_errors['username'].append(f'账号已锁定，请 {remaining_minutes} 分钟后再试')
        elif user and user.check_password(password):
            user.reset_login_attempts()
            session['user_id'] = user.id
            session['username'] = user.username
            flash('登录成功！', 'success')
            return redirect(url_for('auth.index'))
        else:
            field_errors['password'].append('用户名/邮箱或密码错误')
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
            remaining_minutes = int((admin.locked_until - get_china_time()).total_seconds() / 60)
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
    # 如果是管理员，重定向到管理员仪表盘
    if session.get('is_admin'):
        return redirect(url_for('auth.admin_dashboard'))
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

@auth_bp.route('/admin_analytics')
def admin_analytics():
    """数据统计页面"""
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth.admin_login'))
    return render_template('admin_analytics.html')

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
    
    active_count = sum(1 for u in users if not u.is_locked())
    locked_count = sum(1 for u in users if u.is_locked())
    
    return render_template('admin_dashboard.html', admin=admin, users=users, active_count=active_count, locked_count=locked_count)

@auth_bp.route('/admin/user-management')
def user_management():
    """用户管理页面"""
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('auth.admin_login'))
    return render_template('user_management.html')

# ==================== 用户管理API ====================

@auth_bp.route('/api/users')
def get_users():
    """获取用户列表"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    users = User.query.filter_by(is_admin=False).all()
    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'login_attempts': user.login_attempts,
            'locked_until': user.locked_until.strftime('%Y-%m-%d %H:%M:%S') if user.locked_until else None
        })
    
    return jsonify({'success': True, 'users': user_list})

@auth_bp.route('/api/users/search')
def search_users():
    """搜索用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    term = request.args.get('term', '').strip()
    users = User.query.filter(
        User.is_admin == False,
        (User.username.ilike(f'%{term}%') | User.email.ilike(f'%{term}%'))
    ).all()
    
    user_list = []
    for user in users:
        user_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'login_attempts': user.login_attempts,
            'locked_until': user.locked_until.strftime('%Y-%m-%d %H:%M:%S') if user.locked_until else None
        })
    
    return jsonify({'success': True, 'users': user_list})

@auth_bp.route('/api/users/reset-password/<int:user_id>', methods=['POST'])
def reset_password(user_id):
    """重置用户密码"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    user = User.query.get(user_id)
    if not user or user.is_admin:
        return jsonify({'success': False, 'message': '用户不存在'})
    
    # 重置密码为 user@123456
    user.set_password('user@123456')
    user.reset_login_attempts()
    db.session.commit()
    
    return jsonify({'success': True, 'message': '密码重置成功'})

@auth_bp.route('/api/users/lock/<int:user_id>', methods=['POST'])
def lock_user(user_id):
    """锁定/解锁用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    user = User.query.get(user_id)
    if not user or user.is_admin:
        return jsonify({'success': False, 'message': '用户不存在'})
    
    if user.locked_until and user.locked_until > get_china_time():
        # 解锁用户
        user.locked_until = None
        user.login_attempts = 0
    else:
        # 锁定用户
        data = request.get_json(silent=True) or {}
        lock_until_str = data.get('lock_until')
        
        if lock_until_str:
            # 使用自定义锁定时间
            try:
                lock_until = datetime.strptime(lock_until_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return jsonify({'success': False, 'message': '时间格式错误'})
        else:
            # 默认锁定 10 分钟
            lock_until = get_china_time() + timedelta(minutes=10)
        
        user.locked_until = lock_until
    
    db.session.commit()
    return jsonify({'success': True, 'message': '操作成功'})

@auth_bp.route('/api/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    """删除用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    user = User.query.get(user_id)
    if not user or user.is_admin:
        return jsonify({'success': False, 'message': '用户不存在'})
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})

@auth_bp.route('/api/users/create', methods=['POST'])
def create_user():
    """创建用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    
    # 验证输入
    if not username or not email or not password:
        return jsonify({'success': False, 'message': '请填写必要信息'})
    
    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'})
    
    # 检查邮箱是否已存在
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': '邮箱已存在'})
    
    # 检查手机号是否已存在
    if phone and User.query.filter_by(phone=phone).first():
        return jsonify({'success': False, 'message': '手机号已存在'})
    
    # 验证密码强度
    is_valid, msg = User.validate_password_strength(password)
    if not is_valid:
        return jsonify({'success': False, 'message': msg})
    
    # 创建用户
    new_user = User(
        username=username,
        email=email,
        phone=phone,
        is_admin=False
    )
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '用户创建成功'})

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
    
    record_id = request.form.get('record_id', type=int)
    
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
            
            # 获取或创建分类
            category = GarbageCategory.query.filter_by(name=result).first()
            if not category:
                category = GarbageCategory(name=result)
                db.session.add(category)
                db.session.flush()
            
            from app.models import RecognitionRecord
            
            if record_id:
                record = RecognitionRecord.query.get(record_id)
                if record and record.feedback_id is None:
                    record.predicted_category_id = category.id
                    record.confidence = confidence / 100 if confidence > 1 else confidence
                    db.session.commit()
                else:
                    record = None
            
            if not record_id or not record:
                record = RecognitionRecord(
                    user_id=session.get('user_id'),
                    garbage_name='-',
                    predicted_category_id=category.id,
                    confidence=confidence / 100 if confidence > 1 else confidence,
                    is_correct=None
                )
                db.session.add(record)
                db.session.commit()
            
            return jsonify({
                'success': True,
                'result': {
                    'category': result,
                    'confidence': confidence,
                    'time': round(0.1, 2),
                    'record_id': record.id
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
        '厨余垃圾': '厨余垃圾是指居民日常生活及食品加工、饮食服务、单位供餐等活动中产生的垃圾，包括丢弃不用的菜叶、剩菜、剩饭、果皮、蛋壳、茶渣、骨头等。这些垃圾可以通过堆肥等方式进行资源化利用。',
        '可回收物': '可回收物是指适宜回收利用和资源化利用的生活废弃物，如纸类、塑料、玻璃、金属和布料等。这些废弃物可以通过回收再利用，减少对环境的污染，节约资源。',
        '有害垃圾': '有害垃圾是指对人体健康或者自然环境造成直接或者潜在危害的生活废弃物，如废电池、废荧光灯管、废药品、废油漆及其容器等。这些垃圾需要特殊安全处理，避免对环境和人体健康造成危害。',
        '其他垃圾': '其他垃圾是指除可回收物、厨余垃圾、有害垃圾之外的其他生活废弃物，如砖瓦陶瓷、渣土、卫生间废纸、纸巾等难以回收的废弃物。这些垃圾通常采用焚烧或填埋的方式处理。'
    }
    return knowledge_map.get(category, '暂无相关知识')

@auth_bp.route('/confirm-recognition/<int:record_id>', methods=['POST'])
def confirm_recognition(record_id):
    """确认识别结果正确（用户未提交错误反馈）"""
    from app.models import RecognitionRecord
    record = RecognitionRecord.query.get(record_id)
    
    if not record:
        return jsonify({'success': False, 'message': '识别记录不存在'})
    
    if record.feedback_id is not None:
        return jsonify({'success': False, 'message': '该记录已提交反馈'})
    
    if record.is_correct is not None:
        return jsonify({'success': False, 'message': '该记录已确认'})
    
    record.is_correct = True
    db.session.commit()
    
    return jsonify({'success': True, 'message': '已确认识别结果正确'})

@auth_bp.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    """提交反馈"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    real_category = request.form.get('real_category', '').strip()
    note = request.form.get('note', '').strip()
    garbage_name = request.form.get('garbage_name', '-').strip()
    wrong_category = request.form.get('wrong_category', '未知分类').strip()
    confidence = request.form.get('confidence', '0').strip()
    record_id = request.form.get('record_id', '').strip()
    
    if not real_category:
        return jsonify({'success': False, 'message': '请选择真实的垃圾分类'})
    
    # 处理图片（如果有）
    image_path = None
    if 'image' in request.files:
        image = request.files['image']
        if image.filename != '':
            # 确保保存目录存在
            import os
            from werkzeug.utils import secure_filename
            
            upload_folder = os.path.join(os.path.dirname(__file__), '..', 'static', 'feedback_images')
            os.makedirs(upload_folder, exist_ok=True)
            
            # 生成唯一的文件名
            filename = secure_filename(image.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            file_path = os.path.join(upload_folder, unique_filename)
            
            # 保存图片
            image.save(file_path)
            
            # 存储相对路径到数据库
            image_path = f'/static/feedback_images/{unique_filename}'
    
    # 从session中获取用户信息
    user_id = session.get('user_id')
    
    # 查找或创建分类
    def get_or_create_category(name):
        category = GarbageCategory.query.filter_by(name=name).first()
        if not category:
            category = GarbageCategory(name=name)
            db.session.add(category)
            db.session.commit()
        return category
    
    # 获取分类对象
    wrong_category_obj = get_or_create_category(wrong_category)
    correct_category_obj = get_or_create_category(real_category)
    
    # 创建反馈数据
    feedback = Feedback(
        user_id=user_id,
        garbage_name=garbage_name,
        wrong_category_id=wrong_category_obj.id,
        correct_category_id=correct_category_obj.id,
        status='pending',
        image_path=image_path,
        note=note,
        confidence=float(confidence) / 100 if confidence else 0
    )
    
    # 存储反馈数据到数据库
    db.session.add(feedback)
    db.session.flush()
    
    # 如果有识别记录ID，关联反馈记录（不立即判断is_correct，等待管理员处理）
    if record_id:
        from app.models import RecognitionRecord
        record = RecognitionRecord.query.get(int(record_id))
        if record:
            record.garbage_name = garbage_name
            record.actual_category_id = correct_category_obj.id
            record.feedback_id = feedback.id
            record.is_correct = None
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': '反馈提交成功，感谢您的帮助！'})

# ==================== 反馈管理API ====================

@auth_bp.route('/api/feedback/list')
def get_feedback_list():
    """获取反馈列表"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    # 从数据库获取反馈列表
    feedbacks = Feedback.query.order_by(Feedback.created_at.desc()).all()
    
    # 转换为前端需要的格式
    feedback_list = []
    for feedback in feedbacks:
        feedback_list.append({
            'id': feedback.id,
            'user': feedback.user.username,
            'time': feedback.created_at.strftime('%Y-%m-%d %H:%M'),
            'garbageName': feedback.garbage_name,
            'wrongCategory': feedback.wrong_category.name if feedback.wrong_category else '未知分类',
            'correctCategory': feedback.correct_category.name if feedback.correct_category else '未知分类',
            'status': feedback.status
        })
    
    return jsonify({'success': True, 'data': feedback_list})

@auth_bp.route('/api/feedback/details/<int:id>')
def get_feedback_details(id):
    """获取反馈详情"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    # 从数据库获取反馈详情
    feedback = Feedback.query.get(id)
    if not feedback:
        return jsonify({'success': False, 'message': '反馈不存在'})
    
    # 转换为前端需要的格式
    feedback_data = {
        'id': feedback.id,
        'user': feedback.user.username,
        'time': feedback.created_at.strftime('%Y-%m-%d %H:%M'),
        'garbageName': feedback.garbage_name,
        'wrongCategory': feedback.wrong_category.name if feedback.wrong_category else '未知分类',
        'correctCategory': feedback.correct_category.name if feedback.correct_category else '未知分类',
        'status': feedback.status,
        'image': feedback.image_path,
        'note': feedback.note,
        'confidence': f"{int(feedback.confidence * 100)}%" if feedback.confidence else '0%'
    }
    
    return jsonify({'success': True, 'data': feedback_data})

@auth_bp.route('/api/feedback/process/<int:id>', methods=['POST'])
def process_feedback(id):
    """处理反馈"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    status = request.form.get('status', '').strip()
    if status not in ['processed', 'ignored']:
        return jsonify({'success': False, 'message': '无效的状态'})
    
    # 从数据库获取反馈
    feedback = Feedback.query.get(id)
    if not feedback:
        return jsonify({'success': False, 'message': '反馈不存在'})
    
    # 如果状态为已处理，且有图片，则复制图片
    if status == 'processed' and feedback.image_path:
        import os
        import shutil
        
        # 获取正确分类
        correct_category = feedback.correct_category.name if feedback.correct_category else '其他垃圾'
        
        # 确定目标文件夹
        category_map = {
            '厨余垃圾': '1',
            '可回收物': '2',
            '有害垃圾': '3',
            '其他垃圾': '4'
        }
        target_folder = category_map.get(correct_category, '4')
        
        # 构建目标路径
        base_path = os.path.dirname(__file__)
        image_full_path = os.path.join(base_path, '..', feedback.image_path.lstrip('/'))
        target_dir = os.path.join(base_path, '..', 'dataset', 'train', target_folder)
        
        # 确保目标文件夹存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 复制图片
        if os.path.exists(image_full_path):
            # 生成新的文件名
            filename = os.path.basename(image_full_path)
            new_filename = f"feedback_{feedback.id}_{filename}"
            target_path = os.path.join(target_dir, new_filename)
            
            # 复制文件
            shutil.copy2(image_full_path, target_path)
    
    # 更新反馈状态
    feedback.status = status
    
    # 更新关联的识别记录的is_correct字段
    from app.models import RecognitionRecord
    record = RecognitionRecord.query.filter_by(feedback_id=feedback.id).first()
    if record:
        if status == 'processed':
            record.is_correct = False
        elif status == 'ignored':
            record.is_correct = True
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'反馈 {id} 已标记为 {"已处理" if status == "processed" else "已忽略"}'})

@auth_bp.route('/api/feedback/undo/<int:id>', methods=['POST'])
def undo_process_feedback(id):
    """撤回标记"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    # 从数据库获取反馈
    feedback = Feedback.query.get(id)
    if not feedback:
        return jsonify({'success': False, 'message': '反馈不存在'})
    
    # 如果之前是已处理状态，删除已复制的图片
    if feedback.status == 'processed' and feedback.image_path:
        import os
        
        correct_category = feedback.correct_category.name if feedback.correct_category else '其他垃圾'
        
        category_map = {
            '厨余垃圾': '1',
            '可回收物': '2',
            '有害垃圾': '3',
            '其他垃圾': '4'
        }
        target_folder = category_map.get(correct_category, '4')
        
        base_path = os.path.dirname(__file__)
        filename = os.path.basename(feedback.image_path)
        new_filename = f"feedback_{feedback.id}_{filename}"
        target_path = os.path.join(base_path, '..', 'dataset', 'train', target_folder, new_filename)
        
        if os.path.exists(target_path):
            os.remove(target_path)
    
    # 将状态改回待处理
    feedback.status = 'pending'
    
    # 重置关联的识别记录的is_correct字段
    from app.models import RecognitionRecord
    record = RecognitionRecord.query.filter_by(feedback_id=feedback.id).first()
    if record:
        record.is_correct = None
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'反馈 {id} 已撤回标记'})

@auth_bp.route('/api/feedback/filter', methods=['POST'])
def filter_feedback():
    """筛选反馈"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    status = request.form.get('status', 'all').strip()
    category = request.form.get('category', 'all').strip()
    
    # 从数据库筛选反馈
    query = Feedback.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    if category != 'all':
        # 查找对应的分类ID
        category_obj = GarbageCategory.query.filter_by(name=category).first()
        if category_obj:
            query = query.filter_by(correct_category_id=category_obj.id)
    
    feedbacks = query.order_by(Feedback.created_at.desc()).all()
    
    # 转换为前端需要的格式
    filtered_list = []
    for feedback in feedbacks:
        filtered_list.append({
            'id': feedback.id,
            'user': feedback.user.username,
            'time': feedback.created_at.strftime('%Y-%m-%d %H:%M'),
            'garbageName': feedback.garbage_name,
            'wrongCategory': feedback.wrong_category.name if feedback.wrong_category else '未知分类',
            'correctCategory': feedback.correct_category.name if feedback.correct_category else '未知分类',
            'status': feedback.status
        })
    
    return jsonify({'success': True, 'data': filtered_list})

@auth_bp.route('/api/feedback/train', methods=['POST'])
def start_training():
    """开始训练"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    confidence_threshold = request.form.get('confidence_threshold', '70').strip()
    batch_size = request.form.get('batch_size', '50').strip()
    
    # 这里可以添加开始训练的逻辑
    
    return jsonify({'success': True, 'message': '开始训练模型...'})

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """登出"""
    session.clear()
    flash('已成功登出', 'success')
    return redirect(url_for('auth.login'))


# ==================== 数据统计API ====================

@auth_bp.route('/api/analytics/records')
def get_analytics_records():
    """获取识别记录列表（支持分页和筛选）"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    from app.models import RecognitionRecord
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    category = request.args.get('category', '')
    result = request.args.get('result', '')
    name = request.args.get('name', '')
    
    query = RecognitionRecord.query
    
    if start_date:
        query = query.filter(RecognitionRecord.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(RecognitionRecord.created_at < datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    if category:
        category_obj = GarbageCategory.query.filter_by(name=category).first()
        if category_obj:
            query = query.filter(RecognitionRecord.predicted_category_id == category_obj.id)
    if result == 'correct':
        query = query.filter(RecognitionRecord.is_correct == True)
    elif result == 'wrong':
        query = query.filter(RecognitionRecord.is_correct == False)
    elif result == 'unknown':
        query = query.filter(RecognitionRecord.is_correct == None)
    if name:
        query = query.filter(RecognitionRecord.garbage_name.ilike(f'%{name}%'))
    
    total = query.count()


# ==================== 回收点API ====================

@auth_bp.route('/api/recycling-points/nearby', methods=['POST'])
def get_nearby_recycling_points():
    """获取附近回收点"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    data = request.get_json()
    latitude = data.get('latitude', 0)
    longitude = data.get('longitude', 0)
    radius = data.get('radius', 2000)  # 默认2公里
    
    from app.models import RecyclingPoint
    
    # 这里应该使用地理距离计算，这里简化处理
    # 实际项目中应该使用PostGIS或其他地理空间库
    points = RecyclingPoint.query.filter_by(status='active').all()
    
    # 模拟计算距离并排序
    nearby_points = []
    for point in points:
        # 简化的距离计算（实际应该使用Haversine公式）
        distance = ((point.latitude - latitude)**2 + (point.longitude - longitude)**2)**0.5 * 111000  # 转换为米
        if distance <= radius:
            nearby_points.append({
                'id': point.id,
                'name': point.name,
                'address': point.address,
                'distance': f"{distance/1000:.1f}公里",
                'time': point.opening_hours,
                'phone': point.phone,
                'lat': point.latitude,
                'lng': point.longitude,
                'prices': {
                    'paper': f"{point.paper_price:.2f}元/公斤" if point.paper_price else "未知",
                    'plastic': f"{point.plastic_price:.2f}元/公斤" if point.plastic_price else "未知",
                    'metal': f"{point.metal_price:.2f}元/公斤" if point.metal_price else "未知",
                    'glass': f"{point.glass_price:.2f}元/公斤" if point.glass_price else "未知"
                }
            })
    
    # 按距离排序
    nearby_points.sort(key=lambda x: float(x['distance'].replace('公里', '')))
    
    return jsonify({'success': True, 'data': nearby_points[:10]})  # 返回前10个

@auth_bp.route('/api/recycling-points/search', methods=['POST'])
def search_recycling_points():
    """搜索回收点"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    data = request.get_json()
    city = data.get('city', '')
    address = data.get('address', '')
    radius = data.get('radius', 2000)
    
    # 这里应该调用地理编码API将地址转换为经纬度
    # 然后使用附近回收点API
    
    # 模拟数据
    mock_points = [
        {
            'id': 1,
            'name': "绿色家园回收点",
            'address': f"{city}市{address}附近1",
            'distance': "0.5公里",
            'time': "08:00-20:00",
            'phone': "13800138000",
            'lat': 39.915,
            'lng': 116.404,
            'prices': {
                'paper': "1.2元/公斤",
                'plastic': "1.0元/公斤",
                'metal': "1.5元/公斤",
                'glass': "0.2元/公斤"
            }
        },
        {
            'id': 2,
            'name': "环保先锋回收点",
            'address': f"{city}市{address}附近2",
            'distance': "1.2公里",
            'time': "09:00-19:00",
            'phone': "13900139000",
            'lat': 39.918,
            'lng': 116.406,
            'prices': {
                'paper': "1.3元/公斤",
                'plastic': "1.1元/公斤",
                'metal': "1.6元/公斤",
                'glass': "0.3元/公斤"
            }
        },
        {
            'id': 3,
            'name': "循环利用回收点",
            'address': f"{city}市{address}附近3",
            'distance': "1.8公里",
            'time': "08:30-18:30",
            'phone': "13700137000",
            'lat': 39.912,
            'lng': 116.402,
            'prices': {
                'paper': "1.1元/公斤",
                'plastic': "0.9元/公斤",
                'metal': "1.4元/公斤",
                'glass': "0.2元/公斤"
            }
        }
    ]
    
    return jsonify({'success': True, 'data': mock_points})

@auth_bp.route('/api/recycling-points/<int:id>')
def get_recycling_point_detail(id):
    """获取回收点详情"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'})
    
    from app.models import RecyclingPoint
    point = RecyclingPoint.query.get(id)
    
    if not point:
        return jsonify({'success': False, 'message': '回收点不存在'})
    
    point_data = {
        'id': point.id,
        'name': point.name,
        'address': point.address,
        'latitude': point.latitude,
        'longitude': point.longitude,
        'phone': point.phone,
        'opening_hours': point.opening_hours,
        'prices': {
            'paper': f"{point.paper_price:.2f}元/公斤" if point.paper_price else "未知",
            'plastic': f"{point.plastic_price:.2f}元/公斤" if point.plastic_price else "未知",
            'metal': f"{point.metal_price:.2f}元/公斤" if point.metal_price else "未知",
            'glass': f"{point.glass_price:.2f}元/公斤" if point.glass_price else "未知"
        },
        'status': point.status,
        'created_at': point.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': point.updated_at.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return jsonify({'success': True, 'data': point_data})



@auth_bp.route('/api/analytics/export')
def export_analytics_data():
    """导出数据为Excel"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'success': False, 'message': '无权限访问'})
    
    from app.models import RecognitionRecord
    import io
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    category = request.args.get('category', '')
    fields = request.args.get('fields', 'id,garbage_name,predicted_category,actual_category,confidence,is_correct,created_at').split(',')
    
    query = RecognitionRecord.query
    
    if start_date:
        query = query.filter(RecognitionRecord.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(RecognitionRecord.created_at < datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1))
    if category:
        category_obj = GarbageCategory.query.filter_by(name=category).first()
        if category_obj:
            query = query.filter(RecognitionRecord.predicted_category_id == category_obj.id)
    
    records = query.order_by(RecognitionRecord.created_at.desc()).all()
    
    try:
        import pandas as pd
    except ImportError:
        return jsonify({'success': False, 'message': '请安装pandas库: pip install pandas openpyxl'})
    
    data = []
    for record in records:
        row = {}
        if 'id' in fields:
            row['ID'] = record.id
        if 'garbage_name' in fields:
            row['垃圾名称'] = record.garbage_name
        if 'predicted_category' in fields:
            row['预测分类'] = record.predicted_category.name if record.predicted_category else '-'
        if 'actual_category' in fields:
            row['实际分类'] = record.actual_category.name if record.actual_category else '-'
        if 'confidence' in fields:
            row['置信度'] = f"{record.confidence * 100:.1f}%"
        if 'is_correct' in fields:
            if record.is_correct == True:
                row['识别结果'] = '正确'
            elif record.is_correct == False:
                row['识别结果'] = '错误'
            else:
                row['识别结果'] = '未知'
        if 'created_at' in fields:
            row['识别时间'] = record.created_at.strftime('%Y-%m-%d %H:%M:%S')
        data.append(row)
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='识别记录')
    
    output.seek(0)
    
    from flask import send_file
    filename = f"识别记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )