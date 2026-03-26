import pandas as pd
import sqlalchemy as sa
import json
import os
import urllib.parse

print("🚀 开始迁移 train_data.csv 到 MySQL（防重复 + 中文密码支持版）...")

# ==================== 配置区（请仔细修改） ====================
DB_CONFIG = {
    "user": "root",                    # MySQL 用户名
    "password": "wys20050727",            # ←←← 这里填你的 MySQL 密码（支持中文）
    "host": "localhost",
    "port": 3306,
    "database": "garbage_db"
}

# 对密码进行 URL 编码，解决中文密码问题
encoded_password = urllib.parse.quote_plus(DB_CONFIG["password"])

engine = sa.create_engine(
    f"mysql+pymysql://{DB_CONFIG['user']}:{encoded_password}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"
)

csv_path = os.path.join(os.path.dirname(__file__), 'train_data.csv')   # 自动寻找同目录下的 train_data.csv

if not os.path.exists(csv_path):
    print(f"❌ 错误：找不到 train_data.csv 文件！路径：{csv_path}")
    exit(1)

print(f"📄 读取 CSV 文件：{csv_path}")

# 读取并清洗 CSV
df = pd.read_csv(csv_path)

# 数据清洗
df['name'] = df['name'].astype(str).str.strip()
df = df.drop_duplicates(subset=['name'], keep='first')   # 去除 name 重复

# 添加 synonyms（初始为自己）
df['synonyms'] = df['name'].apply(lambda x: json.dumps([x], ensure_ascii=False))

# 只保留需要的列
df = df[['name', 'label', 'synonyms']]

print(f"✅ CSV 读取完成，共 {len(df)} 条记录（去重后）")

# 获取数据库中已存在的 name
try:
    existing_df = pd.read_sql("SELECT name FROM garbage_items", engine)
    existing_names = existing_df['name'].tolist()
    print(f"📊 数据库中已存在 {len(existing_names)} 条记录")
except Exception as e:
    print(f"⚠️ 读取现有记录失败（可能是表不存在），将创建新表: {e}")
    existing_names = []

# 过滤掉已存在的记录
df_new = df[~df['name'].isin(existing_names)]

if df_new.empty:
    print("✅ 所有记录已存在于数据库，无需插入新数据。")
else:
    try:
        df_new.to_sql('garbage_items', engine, if_exists='append', index=False, method='multi', chunksize=500)
        print(f"✅ 迁移成功！本次新增 {len(df_new)} 条记录")
    except Exception as e:
        print(f"❌ 插入失败: {e}")
        exit(1)

# 显示最终统计
total_count = pd.read_sql("SELECT COUNT(*) as cnt FROM garbage_items", engine).iloc[0]['cnt']
print(f"🎉 当前数据库 garbage_items 总记录数：{total_count}")

print("\n✅ 迁移完成！你现在可以启动 server.py 了。")