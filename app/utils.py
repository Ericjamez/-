from flask import current_app
from flask_mail import Message
from app import mail
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import os

# 垃圾分类类别 - 必须与训练代码中的顺序一致
# 训练代码中的顺序：0:厨余垃圾, 1:可回收物, 2:有害垃圾, 3:其他垃圾
TRASH_CLASSES = ['厨余垃圾', '可回收物', '有害垃圾', '其他垃圾']

# 模型加载函数
def load_model():
    """加载训练好的ResNet50模型"""
    model_path = os.path.join('app', 'dataset', 'model', 'best_trash_4class.pth')
    
    # 检查模型文件是否存在
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    
    # 加载ResNet50模型
    from torchvision.models import resnet50
    model = resnet50(pretrained=False)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, len(TRASH_CLASSES))
    
    # 加载训练好的权重
    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    model.eval()
    
    return model

# 图片预处理函数
def preprocess_image(image):
    """预处理图片"""
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    return transform(image).unsqueeze(0)

# 识别图片函数
def recognize_image(image_path):
    """识别垃圾图片"""
    try:
        # 加载模型
        model = load_model()
        
        # 打开并预处理图片
        image = Image.open(image_path).convert('RGB')
        input_tensor = preprocess_image(image)
        
        # 进行预测
        with torch.no_grad():
            outputs = model(input_tensor)
            _, predicted = torch.max(outputs, 1)
            category_idx = predicted.item()
            category = TRASH_CLASSES[category_idx]
            confidence = torch.nn.functional.softmax(outputs, dim=1)[0][category_idx].item()
        
        return True, category, confidence
    except Exception as e:
        return False, str(e), 0.0

def send_email(email, code):
    """发送邮箱验证码"""
    try:
        msg = Message(
            '【垃圾图片分类系统】验证码',
            recipients=[email],
            body=f'您的验证码是：{code}，有效期5分钟，请不要泄露给他人。'
        )
        mail.send(msg)
        return True, '邮件发送成功'
    except Exception as e:
        return False, str(e)