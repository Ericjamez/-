import os
import json
import numpy as np
import pandas as pd
from difflib import SequenceMatcher
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import math

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "my_garbage_model")
DATA_PATH = os.path.join(BASE_DIR, "train_data.csv")

print("启动示例外部 API 服务（用于本地联调）（轻量模式：字符 n-gram embedding）...")

# 轻量替代：使用字符 n-gram 计数向量作为 embedding，避免依赖 transformers/scipy 等大库
CHAR_VOCAB_SIZE = 128

def get_embedding(text, vocab=None, dim=128):
    """基于字符计数的简单向量化：对 unicode 字符取模映射到固定维度并计数，归一化后返回向量。

    目的：提供轻量且确定性的向量以便做最近邻测试，非语义最优但可用于联调流程。
    """
    vec = np.zeros(dim, dtype=float)
    if not text:
        return vec
    for ch in text:
        idx = ord(ch) % dim
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


# 读取训练表作为参照
try:
    df = pd.read_csv(DATA_PATH)
except Exception as e:
    print('无法读取 train_data.csv:', e)
    df = pd.DataFrame(columns=['name', 'label'])

# 建立快速字典：精确匹配与预计算 embedding（可加速）
NAME_TO_LABEL = {}
SAMPLE_NAMES = []
SAMPLE_LABELS = []
SAMPLE_EMBS = []
for _, row in df.iterrows():
    try:
        n = str(row['name'])
        l = int(row['label'])
        NAME_TO_LABEL[n] = l
        SAMPLE_NAMES.append(n)
        SAMPLE_LABELS.append(l)
    except Exception:
        continue

print(f"示例外部 API：加载 {len(SAMPLE_NAMES)} 个训练样本供快速匹配")

for name in SAMPLE_NAMES:
    SAMPLE_EMBS.append(get_embedding(name))
if SAMPLE_EMBS:
    SAMPLE_EMBS = np.stack(SAMPLE_EMBS, axis=0)
else:
    SAMPLE_EMBS = np.zeros((0, 128))


class Query(BaseModel):
    text: str


@app.post('/infer')
async def infer(q: Query):
    text = (q.text or '').strip()
    if not text:
        return {"error": "empty text"}

    # 1) 精确匹配
    if text in NAME_TO_LABEL:
        lbl = NAME_TO_LABEL[text]
        emb = get_embedding(text).tolist()
        return {"label": int(lbl), "category": str(lbl), "confidence": 0.99, "embedding": emb}

    # 2) 模糊匹配
    best_ratio = 0
    best_name = None
    best_label = None
    for name, label in NAME_TO_LABEL.items():
        r = SequenceMatcher(None, text, name).ratio()
        if r > best_ratio:
            best_ratio = r
            best_name = name
            best_label = label

    if best_ratio >= 0.70:
        emb = get_embedding(best_name).tolist()
        return {"label": int(best_label), "category": best_name, "confidence": float(best_ratio), "embedding": emb}

    # 3) 向量最近邻（若可用）
    if SAMPLE_EMBS.size > 0:
        emb_q = get_embedding(text)
        B = SAMPLE_EMBS / (np.linalg.norm(SAMPLE_EMBS, axis=1, keepdims=True) + 1e-10)
        a = emb_q / (np.linalg.norm(emb_q) + 1e-10)
        sims = np.dot(B, a)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])
        if best_sim >= 0.60:
            return {"label": int(SAMPLE_LABELS[best_idx]), "category": SAMPLE_NAMES[best_idx], "confidence": best_sim, "embedding": emb_q.tolist()}

    # 4) 否则返回未知（示例中不调用外部更强模型）
    emb = get_embedding(text).tolist()
    return {"label": None, "category": None, "confidence": 0.0, "embedding": emb}


if __name__ == '__main__':
    # 自动选择一个空闲端口以避免端口占用冲突
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]

    print(f"启动示例外部 API（轻量模式），绑定地址: http://127.0.0.1:{port}/infer")
    uvicorn.run(app, host='127.0.0.1', port=port)
