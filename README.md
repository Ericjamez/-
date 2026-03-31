# 垃圾图片分类系统

一个基于 Flask 和深度学习的智能垃圾分类识别系统，提供完整的用户管理、图片识别、反馈管理、数据分析和游戏化学习功能。

## 📋 项目概述

本项目是一个智能垃圾图片分类系统，利用 PyTorch 深度学习模型实现垃圾图片自动识别分类，同时提供完整的用户认证、反馈管理、数据统计和游戏化学习功能。系统采用 Python Flask 框架开发，使用 MySQL 数据库存储数据，集成智谱 AI 和 DeepSeek API 提供智能问答服务。

## ✨ 功能特性

### 用户认证模块

#### F001 - 用户注册

- 用户可通过用户名、密码、手机号/邮箱完成注册
- 支持手机号和邮箱两种联系方式注册
- 实现手机号/邮箱验证码验证
- 密码强度验证（8位以上，包含字母+数字）
- 账号唯一性校验

#### F002 - 用户登录

- 支持用户名或邮箱登录
- 搭配数字图形验证码，保障账号安全
- 密码使用 SHA256 加密存储
- 安全机制：连续输错5次密码，锁定账号10分钟防刷

#### F003 - 管理员登录

- 管理员使用专属账号密码登录后台
- 登录后可访问管理员专属功能
- 管理员账号仅通过数据库后台添加，不开放页面注册

#### F004 - 密码找回

- 普通用户通过注册时的邮箱接收验证码
- 验证通过后可重置登录密码
- 仅支持普通用户自主找回

### 核心功能模块

#### F005 - 图片识别

- 支持上传图片识别和相机拍照识别两种方式
- 基于 PyTorch 深度学习模型进行垃圾分类
- 识别结果包含：垃圾分类、置信度、识别时间
- 自动展示相关垃圾分类知识
- 支持识别结果反馈（标记错误分类）
- 集成 AI 智能助手浮窗，支持图片问答

#### F006 - 垃圾分类知识库

- 展示四大类垃圾知识：厨余垃圾、可回收物、有害垃圾、其他垃圾
- 提供详细的分类指南和投放建议
- 支持搜索和筛选功能
- 环保小科普内容展示

#### F007 - 反馈管理

- 用户可提交识别错误的反馈
- 管理员可查看和处理用户反馈
- 支持标记为已处理，自动将图片移入训练数据集
- 支持撤回处理操作
- 反馈分类筛选和分页显示
- 管理员可修改垃圾名称

#### F008 - 数据统计

- 识别记录统计（总数、正确识别数）
- 用户活跃度统计
- 反馈数据统计
- 数据可视化图表展示
- 支持数据导出预览和下载

#### F009 - 用户管理

- 管理员可查看所有用户列表
- 支持用户锁定/解锁功能
- 支持重置用户密码
- 支持删除用户账号

### 游戏化学习模块

#### F010 - 分类挑战游戏

- 趣味垃圾分类挑战游戏
- 实时得分和连击系统
- 错题深度分析报告
- AI 智能画像诊断
- 答题实时记录

#### F011 - 勋章墙系统

- 多种环保主题勋章
- 成就解锁机制
- 勋章展示和收集

#### F012 - 碳足迹票据

- 环保贡献证书生成
- 碳减排数据统计
- 支持保存为图片分享

#### F013 - 盲盒系统

- 消耗碳积分抽取环保生物卡片
- 多种稀有度卡片（UR/SSR/SR/N）
- 卡片收集展示
- 开启动画和彩带效果

### AI 智能服务模块

#### F014 - AI 智能助手

- Glassmorphism 风格浮窗设计
- 支持垃圾识别相关问答
- 支持查看上传图片并回答问题
- 可拖拽交互设计
- 快捷问题按钮

#### F015 - 智能运维诊断

- 系统健康状态监控
- 数据库连接检测
- 模型加载状态检测
- 系统资源使用监控

#### F016 - 回收站点地图

- 附近回收点地图展示
- 回收站点位置查询
- 导航功能支持

## 🏗️ 项目结构

```
.
├── app/                        # 应用主目录
│   ├── __init__.py            # 应用初始化
│   ├── models.py              # 数据库模型
│   ├── utils.py               # 工具函数
│   ├── ai_service.py          # AI 服务模块
│   ├── routes/                # 路由目录
│   │   ├── __init__.py
│   │   └── auth.py            # 认证和业务路由
│   ├── templates/             # 模板目录
│   │   ├── base.html          # 基础模板
│   │   ├── index.html         # 首页
│   │   ├── register.html      # 注册页
│   │   ├── login.html         # 登录页
│   │   ├── admin_login.html   # 管理员登录页
│   │   ├── forgot_password.html # 忘记密码页
│   │   ├── dashboard.html     # 用户仪表盘
│   │   ├── admin_dashboard.html # 管理员仪表盘
│   │   ├── recognition.html   # 图片识别页
│   │   ├── knowledge.html     # 知识库页
│   │   ├── feedback.html      # 反馈管理页
│   │   ├── admin_analytics.html # 数据统计页
│   │   ├── user_management.html # 用户管理页
│   │   ├── analytics.html     # 用户数据分析页
│   │   ├── GameStation.html   # 分类挑战游戏页
│   │   ├── AnalyticsDashboard.html # 智能运维诊断页
│   │   └── map.html           # 回收站点地图页
│   ├── static/                # 静态文件目录
│   │   ├── background/        # 背景图片和卡片图片
│   │   └── feedback_images/   # 反馈图片存储
│   └── dataset/               # 数据集目录
│       ├── model/             # 模型文件
│       │   └── best_trash_4class.pth
│       └── train/             # 训练数据
│           ├── 1/             # 厨余垃圾
│           ├── 2/             # 可回收物
│           ├── 3/             # 有害垃圾
│           └── 4/             # 其他垃圾
├── docs/                      # 文档目录
│   └── recognition-api.md     # 识别页面API文档
├── config.py                  # 配置文件
├── run.py                     # 应用启动文件
├── requirements.txt           # 依赖列表
└── README.md                  # 项目文档
```

## 🚀 快速开始

### 环境要求

- Python 3.11+
- MySQL 8.0+
- Flask 3.0.0

### 安装依赖

```bash
pip install -r requirements.txt
```

### 数据库配置

1. 创建 MySQL 数据库：

```sql
CREATE DATABASE waste CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

1. 修改 `config.py` 中的数据库连接配置：

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/waste'
```

1. 初始化数据库表（首次运行自动创建）

### 运行项目

```bash
python run.py
```

项目将运行在 `http://localhost:5000`

### 端口配置

项目默认使用端口 5000，可通过环境变量 `DEPLOY_RUN_PORT` 修改：

```bash
export DEPLOY_RUN_PORT=5000
python run.py
```

## 📊 数据库设计

### 用户表

| 字段名             | 类型          | 说明           |
| --------------- | ----------- | ------------ |
| id              | Integer     | 主键           |
| username        | String(80)  | 用户名（唯一）      |
| password\_hash  | String(255) | 密码哈希（SHA256） |
| phone           | String(20)  | 手机号（唯一）      |
| email           | String(120) | 邮箱（唯一）       |
| is\_admin       | Boolean     | 是否为管理员       |
| login\_attempts | Integer     | 登录失败次数       |
| locked\_until   | DateTime    | 锁定截止时间       |
| created\_at     | DateTime    | 创建时间         |
| updated\_at     | DateTime    | 更新时间         |

### 验证码表 (verification\_codes)

| 字段名         | 类型          | 说明     |
| ----------- | ----------- | ------ |
| id          | Integer     | 主键     |
| contact     | String(120) | 手机号或邮箱 |
| code        | String(10)  | 验证码    |
| code\_type  | String(20)  | 验证码类型  |
| created\_at | DateTime    | 创建时间   |
| expires\_at | DateTime    | 过期时间   |
| used        | Boolean     | 是否已使用  |

### 识别记录表 (recognition\_records)

| 字段名                 | 类型          | 说明   |
| ------------------- | ----------- | ---- |
| id                  | Integer     | 主键   |
| user\_id            | Integer     | 用户ID |
| image\_path         | String(255) | 图片路径 |
| predicted\_category | String(50)  | 预测分类 |
| confidence          | Float       | 置信度  |
| is\_correct         | Boolean     | 是否正确 |
| real\_category      | String(50)  | 真实分类 |
| created\_at         | DateTime    | 创建时间 |

### 反馈表

| 字段名             | 类型          | 说明     |
| --------------- | ----------- | ------ |
| id              | Integer     | 主键     |
| user\_id        | Integer     | 用户ID   |
| record\_id      | Integer     | 识别记录ID |
| garbage\_name   | String(100) | 垃圾名称   |
| wrong\_category | String(50)  | 错误分类   |
| real\_category  | String(50)  | 正确分类   |
| image\_path     | String(255) | 图片路径   |
| confidence      | Float       | 置信度    |
| note            | Text        | 备注     |
| status          | String(20)  | 状态     |
| created\_at     | DateTime    | 创建时间   |
| processed\_at   | DateTime    | 处理时间   |

### 游戏错误记录表 (game\_mistakes)

| 字段名            | 类型          | 说明     |
| -------------- | ----------- | ------ |
| id             | Integer     | 主键     |
| user\_id       | Integer     | 用户ID   |
| item\_name     | String(100) | 物品名称   |
| wrong\_label   | Integer     | 错误分类标签 |
| correct\_label | Integer     | 正确分类标签 |
| created\_at    | DateTime    | 创建时间   |

## 🔐 安全特性

1. **密码加密**：使用 SHA256 算法对密码进行哈希加密存储
2. **登录防刷**：连续5次登录失败后锁定账号10分钟
3. **验证码机制**：
   - 图形验证码：防止自动化攻击
   - 邮箱验证码：验证用户身份
4. **账号唯一性**：用户名、手机号、邮箱均需唯一
5. **密码强度要求**：至少8位，包含字母和数字
6. **会话管理**：使用 Flask-Login 管理用户会话

## 📝 API 路由

### 页面路由

| 路由                    | 方法       | 说明             |
| --------------------- | -------- | -------------- |
| `/`                   | GET      | 首页             |
| `/register`           | GET/POST | 用户注册           |
| `/login`              | GET/POST | 用户登录（支持用户名/邮箱） |
| `/admin/login`        | GET/POST | 管理员登录          |
| `/forgot-password`    | GET/POST | 密码找回           |
| `/dashboard`          | GET      | 用户中心           |
| `/admin/dashboard`    | GET      | 管理员中心          |
| `/recognition`        | GET      | 图片识别页          |
| `/knowledge`          | GET      | 知识库页           |
| `/feedback`           | GET      | 反馈管理页          |
| `/admin/analytics`    | GET      | 数据统计页          |
| `/admin/users`        | GET      | 用户管理页          |
| `/GameStation`        | GET      | 分类挑战游戏页（环保训练）   |
| `/AnalyticsDashboard` | GET      | 智能运维诊断页        |
| `/map`                | GET      | 回收站点地图页        |
| `/logout`             | GET/POST | 退出登录           |

### API 接口

| 接口                               | 方法   | 说明       |
| -------------------------------- | ---- | -------- |
| `/send-verification-code`        | POST | 发送验证码    |
| `/recognize`                     | POST | 图片识别     |
| `/confirm-recognition`           | POST | 确认识别结果   |
| `/submit-feedback`               | POST | 提交反馈     |
| `/api/feedback/list`             | GET  | 获取反馈列表   |
| `/api/feedback/details/<id>`     | GET  | 获取反馈详情   |
| `/api/feedback/process/<id>`     | POST | 处理反馈     |
| `/api/feedback/undo/<id>`        | POST | 撤回处理     |
| `/api/users/lock/<id>`           | POST | 锁定用户     |
| `/api/users/reset-password/<id>` | POST | 重置密码     |
| `/api/users/delete/<id>`         | POST | 删除用户     |
| `/api/predict`                   | POST | 预测垃圾分类   |
| `/api/log_game_mistake`          | POST | 记录游戏错误   |
| `/api/get_ai_analysis`           | POST | 获取AI分析报告 |
| `/api/draw_card`                 | GET  | 抽取盲盒卡片   |
| `/api/ai_chat`                   | POST | AI智能问答   |
| `/api/export/preview`            | GET  | 导出数据预览   |
| `/api/export/csv`                | GET  | 导出CSV文件  |

## 🤖 AI 服务配置

系统集成了智谱 AI 和 DeepSeek API，提供智能问答服务。

### 配置 API 密钥

在 `config.py` 中配置：

```python
# 智谱 AI 配置（用于图片识别和问答）
ZHIPU_API_KEY = 'your_zhipu_api_key'

# DeepSeek 配置（用于文本问答）
DEEPSEEK_API_KEY = 'your_deepseek_api_key'
```

### AI 功能

1. **图片识别问答**：上传图片后可直接询问 AI 关于垃圾分类的问题
2. **游戏分析报告**：根据游戏表现生成个性化建议
3. **智能助手浮窗**：在识别页面提供实时问答服务

## 👤 管理员账号创建

管理员账号需要通过数据库直接创建，不提供页面注册入口。可以使用以下 Python 脚本创建：

```python
from app import create_app
from app.models import db, User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123456')
        db.session.add(admin)
        db.session.commit()
        print("管理员账号创建成功！")
    else:
        print("管理员账号已存在！")
```

## ⚙️ 配置说明

主要配置项位于 `config.py` 文件中：

```python
class Config:
    SECRET_KEY = 'dev-secret-key-change-in-production'  # 会话密钥
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@localhost/waste'  # 数据库连接
    MAX_LOGIN_ATTEMPTS = 5  # 最大登录失败次数
    LOCKOUT_TIME_MINUTES = 10  # 锁定时间（分钟）
    PASSWORD_MIN_LENGTH = 8  # 密码最小长度
    
    # 邮箱服务配置
    MAIL_SERVER = 'smtp.qq.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'your_email@qq.com'
    MAIL_PASSWORD = 'your_smtp_password'
    
    # AI 服务配置
    ZHIPU_API_KEY = 'your_zhipu_api_key'
    DEEPSEEK_API_KEY = 'your_deepseek_api_key'
```

生产环境部署时，请务必修改 `SECRET_KEY` 和数据库密码。

## 📦 依赖包

```
Flask==3.0.0              # Web 框架
Flask-SQLAlchemy==3.1.1   # ORM 数据库工具
Flask-Login==0.6.3        # 用户会话管理
Flask-Mail==0.9.1         # 邮件发送
email-validator==2.1.0    # 邮箱验证
Werkzeug==3.0.1           # WSGI 工具
pymysql==1.0.3            # MySQL 驱动
Pillow==10.1.0            # 图像处理
torch==2.1.0              # 深度学习框架
torchvision==0.16.0       # 图像处理工具
numpy                     # 数值计算
openpyxl                  # Excel 文件处理
zhipuai                   # 智谱 AI SDK
requests                  # HTTP 请求
```

## 🔧 部署说明

### 开发环境

```bash
pip install -r requirements.txt
python run.py
```

### 生产环境

建议使用 Gunicorn 部署：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### 数据库共享配置

如需多用户共享数据库：

1. 修改 MySQL 配置允许远程访问
2. 创建远程访问用户并授权
3. 配置防火墙开放 3306 端口
4. 客户端使用服务器 IP 连接

## 🎨 页面预览

| 页面     | 说明                |
| ------ | ----------------- |
| 首页     | 系统入口，展示核心功能和环保科普  |
| 登录页    | 支持用户名/邮箱登录，图形验证码  |
| 注册页    | 手机号/邮箱验证码注册       |
| 图片识别页  | 上传图片或拍照识别，AI助手浮窗  |
| 知识库页   | 四大垃圾分类知识展示        |
| 分类挑战   | 趣味游戏，勋章墙，碳足迹票据，盲盒 |
| 回收站点   | 附近回收点地图查询        |
| 用户中心   | 个人信息和识别历史         |
| 管理员仪表盘 | 系统概览和用户统计         |
| 反馈管理   | 用户反馈列表和处理         |
| 数据统计   | 识别数据可视化分析，导出功能    |
| 用户管理   | 用户列表和账户管理         |
| 智能运维   | 系统健康状态监控和诊断       |

## 🎮 游戏化功能

### 分类挑战

- 限时分类挑战，提升分类技能
- 连击系统增加趣味性
- 错题自动记录和分析

### 勋章系统

| 勋章 | 名称     | 获取条件       |
| -- | ------ | ---------- |
| 🌱 | 初级分类员  | 首次正确分类     |
| ⚡  | 连击大师   | 连续10次正确    |
| ☣️ | 剧毒终结者  | 正确分类5件有害垃圾 |
| 🌍 | 碳中和小能手 | 得分超过300分   |
| 💯 | 完美主义   | 单局全部正确     |
| 🏆 | 冠军     | 打破最高分记录    |

### 盲盒卡片

| 稀有度 | 卡片       | 概率    |
| --- | -------- | ----- |
| UR  | 大熊猫      | 5%    |
| SSR | 华南虎、极地企鹅 | 15%×2 |
| SR  | 长江江豚、绿孔雀 | 15%×2 |
| N   | 环保卫士     | 35%   |

## 📌 注意事项

1. **深度学习模型**：模型文件位于 `app/dataset/model/best_trash_4class.pth`
2. **训练数据**：处理后的反馈图片会自动加入训练数据集
3. **邮箱配置**：需要配置有效的 SMTP 服务才能发送验证码邮件
4. **管理员账号**：管理员账号必须通过数据库创建
5. **数据库安全**：生产环境建议使用强密码和 SSL 连接
6. **AI 服务**：需要配置有效的 API 密钥才能使用智能问答功能
7. **盲盒卡片图片**：卡片图片位于 `app/static/background/` 目录

## 🤝 后续功能规划

- [x] 分类挑战游戏
- [x] AI 智能助手
- [x] 盲盒系统
- [x] 勋章墙
- [x] 碳足迹票据
- [x] 回收站点地图功能
- [ ] 用户识别历史记录详情
- [ ] 模型在线训练和更新
- [ ] 移动端适配优化
- [ ] 第三方登录（微信、QQ等）
- [ ] 系统操作日志
- [ ] 社区分享功能

## 📄 许可证

MIT License

## 👨‍💻 作者

垃圾图片分类系统开发团队

***

**最后更新时间**：2026年3月
