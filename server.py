import os
import torch
import uvicorn
import pandas as pd
import numpy as np
import sqlalchemy as sa
import json
from fastapi import FastAPI, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from transformers import BertTokenizer, BertForSequenceClassification, BertModel
from rapidfuzz import fuzz, process
import requests
import logging
from functools import lru_cache

# 基础设置
logging.basicConfig(level=logging.INFO)
os.environ["TRANSFORMERS_OFFLINE"] = "1"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ====================== 配置区 ======================
TIAN_API_KEY = "31c7eedeac3fe824f52aac2b6d3d5573"
DB_PWD = "wys20050727" 
MODEL_PATH = os.path.join(os.path.dirname(__file__), "my_garbage_model")

LABEL_MAP = {1: "可回收垃圾", 2: "有害垃圾", 4: "湿垃圾", 8: "干垃圾", 16: "大件垃圾"}

# 数据库引擎
engine = sa.create_engine(f"mysql+pymysql://root:{DB_PWD}@localhost:3306/garbage_db", pool_pre_ping=True)

# 模型加载
try:
    tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
    classifier = BertForSequenceClassification.from_pretrained(MODEL_PATH)
    base_model = BertModel.from_pretrained(MODEL_PATH)
    classifier.eval()
    base_model.eval()
except:
    classifier = None
    base_model = None


@lru_cache(maxsize=1024)
def get_semantic_emb(text):
    if base_model is None or tokenizer is None:
        return np.zeros(768)
    inputs = tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=32)
    with torch.no_grad():
        out = base_model(**inputs)
        emb = out.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()
        norm = np.linalg.norm(emb) + 1e-8
        return emb / norm

# ====================== 1. 数据库驱动的建议生成器 (一对一) ======================

def generate_guide_from_db(item_id: int, label_val: int, item_name: str) -> str:
    """严格按照数据库层级获取建议"""
    with engine.connect() as conn:
        # A. 优先尝试：获取特定物品的专属建议 (item_specific_guides)
        spec_query = sa.text("SELECT full_guide FROM item_specific_guides WHERE item_id = :id")
        spec_res = conn.execute(spec_query, {"id": item_id}).fetchone()
        if spec_res:
            return spec_res[0]

        # B. 次选方案：根据类别标签组合模块化建议 (guide_components)
        comp_query = sa.text("""
            SELECT text_template FROM guide_components 
            WHERE category_label = :lbl 
            ORDER BY priority DESC, RAND() LIMIT 3
        """)
        comps = conn.execute(comp_query, {"lbl": label_val}).fetchall()
        if comps:
            parts = [c[0].replace("{item}", item_name) for c in comps]
            return "。".join(parts) + "。"

    return f"请将其投放到{LABEL_MAP.get(label_val, '干垃圾')}桶中。"

# ====================== 2. 自动学习与纠偏逻辑 ======================

def learn_and_save(name: str, label: int):
    """当 API 给出结果时，同步到本地数据库"""
    try:
        with engine.connect() as conn:
            query = sa.text("""
                INSERT INTO garbage_items (name, label, synonyms) 
                VALUES (:n, :l, :s) 
                ON DUPLICATE KEY UPDATE label = VALUES(label)
            """)
            conn.execute(query, {"n": name, "l": label, "s": json.dumps([name], ensure_ascii=False)})
            conn.commit()
    except Exception as e:
        logging.error(f"学习入库失败: {e}")

# ====================== 3. 推理逻辑 ======================

class Item(BaseModel):
    name: str

@app.post("/predict")
async def predict(item: Item):
    text = item.name.strip()
    if not text: return {"category": "未知", "confidence": 0, "guide": "请输入名称"}

    # --- 阶段 A: 本地数据库精准匹配 ---
    with engine.connect() as conn:
        db_res = conn.execute(sa.text("SELECT id, label, name FROM garbage_items WHERE name = :t"), {"t": text}).fetchone()
        if db_res:
            item_id, lbl, std_name = db_res
            return {
                "category": LABEL_MAP[lbl],
                "confidence": 1.0,
                "method": "本地数据库精准命中",
                "guide": generate_guide_from_db(item_id, lbl, std_name)
            }

    # --- 阶段 B: BERT 算法预测 ---
    bert_lbl, bert_conf = 8, 0.0
    if classifier:
        inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=32)
        with torch.no_grad():
            logits = classifier(**inputs).logits
            probs = torch.nn.functional.softmax(logits, dim=-1)[0].numpy()
            idx_map = {0: 1, 1: 2, 2: 4, 3: 8, 4: 16}
            top_idx = np.argmax(probs)
            bert_lbl = idx_map[top_idx]
            bert_conf = float(probs[top_idx])

        # 语义向量比对：计算与每类原型的余弦相似度
        vec_conf = 0.0
        vec_lab = bert_lbl
        try:
            target_emb = get_semantic_emb(text)
            sims = []
            for l_val in [1,2,4,8]:
                with engine.connect() as conn:
                    rows = conn.execute(sa.text("SELECT name FROM garbage_items WHERE label = :l LIMIT 20"), {"l": l_val}).fetchall()
                    if not rows:
                        sims.append(0.0)
                        continue
                    protos = [r[0] for r in rows]
                    proto_embs = [get_semantic_emb(p) for p in protos]
                    proto_mean = np.mean(proto_embs, axis=0)
                    sim = float(np.dot(target_emb, proto_mean))
                    sims.append(sim)
            idx_max = int(np.argmax(sims))
            vec_lab = [1,2,4,8][idx_max]
            vec_conf = float(sims[idx_max])
        except Exception:
            vec_conf = 0.0

    # --- 阶段 C: 权威 API 校验与纠偏 ---
    # 如果 BERT 置信度不高，或者为了绝对准确，调用 API
    api_suggested = False
    suggested_name = None
    suggested_label = None
    if bert_conf < 0.85:
        try:
            url = f"https://apis.tianapi.com/lajifenlei/index?key={TIAN_API_KEY}&word={text}"
            api_data = requests.get(url, timeout=2).json()
            if api_data.get("code") == 200:
                res = api_data["result"]["list"][0]
                api_lbl = {0:1, 1:2, 2:4, 3:8}.get(res["type"], 8)
                
                # 建议由 API 提供，但不自动写入数据库，改为返回给前端作为待审计 suggestion
                api_suggested = True
                suggested_name = res["name"]
                suggested_label = api_lbl
                # 返回 API 建议但不学习入库，前端可将其放入纠正池等待人工确认
                return {
                    "category": LABEL_MAP[api_lbl],
                    "confidence": 0.99,
                    "method": "天行官方API",
                    "guide": res.get('explain', '') or res.get('tip', ''),
                    "api_suggested": True,
                    "suggested_name": suggested_name,
                    "suggested_label": suggested_label,
                    "bert_conf": round(bert_conf, 3),
                    "vec_conf": round(vec_conf, 3)
                }
        except: pass

    # 兜底返回 BERT 结果，并附带 token 切分与每 token 的向量模长，同时返回 bert/vec 置信度
    tokens = []
    token_norms = []
    try:
        if base_model is not None and tokenizer:
            inp = tokenizer(text, return_tensors='pt', truncation=True, max_length=32)
            with torch.no_grad():
                out = base_model(**inp)
                last = out.last_hidden_state.squeeze(0).cpu().numpy()
                ids = inp['input_ids'][0].tolist()
                tokens = tokenizer.convert_ids_to_tokens(ids)
                token_norms = [round(float(x), 2) for x in (np.linalg.norm(last, axis=1).tolist())]
    except Exception:
        tokens = []
        token_norms = []

    # 简单融合：加权 BERT 与向量相似度作为最终置信度
    try:
        final_conf = float(round(0.65 * bert_conf + 0.35 * (vec_conf if vec_conf is not None else 0.0), 3))
    except Exception:
        final_conf = round(bert_conf, 3)

    return {
        "category": LABEL_MAP[bert_lbl],
        "confidence": final_conf,
        "method": "BERT 算法推理",
        "guide": f"基于算法模型，建议投放到{LABEL_MAP[bert_lbl]}桶。",
        "tokens": tokens,
        "token_norms": token_norms,
        "bert_conf": round(bert_conf, 3),
        "vec_conf": round(vec_conf, 3)
    }

# ====================== 4. 新增：人工纠正接口 ======================
class Correction(BaseModel):
    name: str
    correct_category: str

@app.post("/correct")
async def correct(c: Correction):
    """运维中心调用的纠正接口，实时修改数据库"""
    try:
        # 转换文字为数字标签
        inv_map = {v: k for k, v in LABEL_MAP.items()}
        lbl = inv_map.get(c.correct_category)
        if not lbl: return {"ok": False, "error": "类别名称无效"}

        with engine.connect() as conn:
            # 更新或插入主表
            conn.execute(sa.text("""
                INSERT INTO garbage_items (name, label, synonyms) 
                VALUES (:n, :l, :s) 
                ON DUPLICATE KEY UPDATE label = VALUES(label)
            """), {"n": c.name, "l": lbl, "s": json.dumps([c.name], ensure_ascii=False)})
            conn.commit()
        return {"ok": True, "new_confidence": 1.0, "source": "人工纠正(已入库)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)