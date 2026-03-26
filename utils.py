from flask import current_app
from flask_mail import Message
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models

def send_sms(phone_number, code):
    """发送短信验证码"""
    try:
        config = open_api_models.Config(
            access_key_id=current_app.config['ALIBABA_CLOUD_ACCESS_KEY_ID'],
            access_key_secret=current_app.config['ALIBABA_CLOUD_ACCESS_KEY_SECRET']
        )
        config.endpoint = 'dysmsapi.aliyuncs.com'
        
        client = Dysmsapi20170525Client(config)
        send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
            phone_numbers=phone_number,
            sign_name=current_app.config['SMS_SIGN_NAME'],
            template_code=current_app.config['SMS_TEMPLATE_CODE'],
            template_param=f'{{"code":"{code}"}}'
        )
        
        response = client.send_sms(send_sms_request)
        return True, response.body.message
    except Exception as e:
        return False, str(e)

def send_email(email, code):
    """发送邮箱验证码"""
    try:
        from app import mail
        msg = Message(
            '【垃圾图片分类系统】验证码',
            recipients=[email],
            body=f'您的验证码是：{code}，有效期5分钟，请不要泄露给他人。'
        )
        mail.send(msg)
        return True, '邮件发送成功'
    except Exception as e:
        return False, str(e)