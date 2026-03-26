import os
import traceback
from app import create_app

try:
    print("正在创建应用...")
    app = create_app()
    print("应用创建成功！")
    
    if __name__ == '__main__':
        port = int(os.environ.get('DEPLOY_RUN_PORT', 5000))
        print(f"正在启动服务器，端口：{port}...")
        app.run(host='0.0.0.0', port=port, debug=True)
except Exception as e:
    print(f"启动失败：{e}")
    traceback.print_exc()
