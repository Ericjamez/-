import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:root@localhost/waste'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_TIME_MINUTES = 10
    PASSWORD_MIN_LENGTH = 8
    
    # 邮箱服务配置（QQ邮箱）
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.qq.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or '3124418793@qq.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'jlwommqicavbdhcj'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or '3124418793@qq.com'
    
    # DeepSeek AI 配置
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY') or 'sk-1fbb9f457dd94b44b90bb75de052e29f'
    DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
    
    # 智谱 GLM-4V 图片识别配置
    GLM_API_KEY = os.environ.get('GLM_API_KEY') or 'a49badba035849169ff20e7d78d79438.AWZt2Ze5Dod5CQ7X'
    GLM_API_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
    GLM_VISION_MODEL = 'glm-4v'
    
    # 天行 API 配置（垃圾分类纠偏）
    TIAN_API_KEY = os.environ.get('TIAN_API_KEY') or '31c7eedeac3fe824f52aac2b6d3d5573'
    
    # BERT 模型路径
    BERT_MODEL_PATH = os.environ.get('BERT_MODEL_PATH') or os.path.join(os.path.dirname(__file__), 'app', 'dataset', 'my_garbage_model')
    ZHIPU_API_KEY = "69c729c061af4cf590f6079d0ea1c1cb.J7RQE5IslWO6rnzT" 