from flask import Flask
from config import Config
from app.models import db,GarbageCategory
from flask_mail import Mail

mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 初始化数据库
    db.init_app(app)
    
    # 初始化邮箱服务
    mail.init_app(app)
    
    # 初始化 BERT 模型
    try:
        from app.ai_service import init_bert_model
        init_bert_model(app)
    except Exception as e:
        print(f"BERT 模型初始化失败: {e}")
    
    # 创建所有表
    with app.app_context():
        db.create_all()
        # 初始化垃圾分类数据

        if GarbageCategory.query.count() == 0:
            garbage_categories = [
                {
                    'name': '厨余垃圾',
                    'description': '易腐烂的生物质生活废弃物，包括剩菜剩饭、果皮、蔬菜叶、肉类废弃物等'
                },
                {
                    'name': '可回收物',
                    'description': '适宜回收利用和资源化利用的生活废弃物，包括废纸、塑料、玻璃、金属、布料等'
                },
                {
                    'name': '有害垃圾',
                    'description': '对人体健康或自然环境造成直接或潜在危害的生活废弃物，包括电池、灯管、过期药品、油漆桶等'
                },
                {
                    'name': '其他垃圾',
                    'description': '除可回收物、厨余垃圾、有害垃圾外的其他生活废弃物，包括砖瓦陶瓷、渣土、卫生间废纸等'
                }
            ]
            
            for category_data in garbage_categories:
                category = GarbageCategory(**category_data)
                db.session.add(category)
            
            db.session.commit()
            print("成功初始化垃圾分类表数据")
    # 注册蓝图
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    return app
