import os
import torch
import torch.nn as nn
import uvicorn
import pandas as pd
import numpy as np
import sqlalchemy as sa
import json
import datetime
import requests
import logging
from fastapi import FastAPI, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from transformers import BertTokenizer, BertForSequenceClassification, BertModel
from rapidfuzz import fuzz, process
from functools import lru_cache

# ====================== 基础配置 ======================
logging.basicConfig(level=logging.INFO)
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ====================== 配置参数 ======================
TIAN_API_KEY = "31c7eedeac3fe824f52aac2b6d3d5573"
DB_PWD = "wys20050727"
MODEL_PATH = os.path.join(os.path.dirname(__file__), "my_garbage_model")
LABEL_MAP = {
    1: "可回收垃圾",
    2: "有害垃圾",
    4: "湿垃圾",
    8: "干垃圾",
    16: "大件垃圾"
}

# ====================== 数据库初始化 ======================
DB_URL = f"mysql+pymysql://root:{DB_PWD}@localhost:3306/garbage_db?charset=utf8mb4"
USE_MYSQL = False
engine = None

try:
    engine = sa.create_engine(DB_URL, pool_pre_ping=True)
    with engine.connect() as _c:
        _c.execute(sa.text("SELECT 1"))
    USE_MYSQL = True
    print("✅ 数据库连接成功")
except Exception as e:
    USE_MYSQL = False
    engine = None
    logging.error(f"❌ 数据库连接失败：{str(e)}")

# ====================== 模型加载 ======================
try:
    tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
    
    # 修改这一行：明确指定使用 "eager" 模式，以支持 output_attentions
    classifier = BertForSequenceClassification.from_pretrained(
        MODEL_PATH, 
        output_attentions=True,
        attn_implementation="eager"  # <--- 添加这一行
    )
    
    base_model = BertModel.from_pretrained(MODEL_PATH)
    classifier.eval()
    base_model.eval()
    print("✅ BERT 模型加载成功 (XAI 模式已启用)")
except Exception as e:
    classifier = base_model = tokenizer = None
    print(f"⚠️ 模型加载失败：{e}")

# ====================== LSTM 预测 ======================
class GarbageLSTM(nn.Module):
    def __init__(self):
        super(GarbageLSTM, self).__init__()
        self.lstm = nn.LSTM(1, 64, 2, batch_first=True)
        self.fc = nn.Linear(64, 1)
    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

@app.get("/predict_flow")
async def predict_flow():
    now = datetime.datetime.now()
    labels = [(now + datetime.timedelta(hours=i)).strftime("%H:00") for i in range(24)]
    data = [round(30 * np.sin(i/3.8) + 50 + float(np.random.normal(0,3)), 2) for i in range(24)]
    return {"labels": labels, "data": data}

# ====================== 语义关联工具 ======================
@lru_cache(maxsize=512)
def get_emb(text):
    if not base_model or not tokenizer:
        return np.zeros(768)
    inputs = tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=32)
    with torch.no_grad():
        out = base_model(**inputs)
        return out.last_hidden_state.mean(dim=1).squeeze().numpy()

def get_related(text, lbl_val):
    if not USE_MYSQL or not engine:
        return []
    try:
        target = get_emb(text)
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT name FROM garbage_items WHERE label = :l LIMIT 50"),
                {"l": lbl_val}
            ).fetchall()
            sims = []
            for r in rows:
                emb = get_emb(r[0])
                score = np.dot(target, emb) / (np.linalg.norm(target) * np.linalg.norm(emb) + 1e-8)
                sims.append((r[0], score))
            sims.sort(key=lambda x: x[1], reverse=True)
            return [x[0] for x in sims[1:4]]
    except:
        return []

# ====================== 【增强】模糊匹配同义词 ======================
def fuzzy_match_item(text):
    if not USE_MYSQL or not engine:
        return None
    try:
        with engine.connect() as conn:
            items = conn.execute(sa.text("SELECT id, name, label, synonyms FROM garbage_items")).fetchall()
        candidates = []
        for it in items:
            cname = it[1].strip()
            syns = json.loads(it[3]) if it[3] else []
            all_names = [cname] + syns
            for n in all_names:
                score = fuzz.ratio(text.lower(), n.lower())
                if score > 75:
                    candidates.append((it, score))
                    break
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0][0]
        return {"id": best[0], "name": best[1], "label": best[2]}
    except:
        return None

# ====================== 【增强】模块化组件生成投放建议 ======================
def generate_guide(item_name, label):
    if not USE_MYSQL or not engine:
        return None
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("""
                    SELECT text_template FROM guide_components
                    WHERE category_label = :l
                    ORDER BY priority DESC
                """), {"l": label}
            ).fetchall()
        parts = []
        for r in rows:
            txt = r[0].replace("{item}", item_name)
            parts.append(txt)
        if parts:
            return "；".join(parts) + "。"
    except:
        return None

# ====================== XAI 可解释性：注意力权重 ======================
def get_attention_weights(text):
    if not tokenizer or not classifier:
        return [], []
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=32)
        with torch.no_grad():
            outputs = classifier(**inputs, output_attentions=True)
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        attn = outputs.attentions[-1][0].mean(dim=0).mean(dim=0).numpy()
        attn = (attn - attn.min()) / (attn.max() - attn.min() + 1e-8)
        return tokens, attn.tolist()
    except:
        return [], []

# ====================== 核心预测逻辑（已增强） ======================
class Item(BaseModel):
    name: str

@app.post("/predict")
async def predict(item: Item):
    text = item.name.strip()
    if not text:
        return {"category": "未知", "confidence": 0}

    final_guide = None
    matched_item = None

    # 1. 精准匹配
    if USE_MYSQL and engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(sa.text("""
                    SELECT gi.id, gi.label, gi.name, isg.full_guide
                    FROM garbage_items gi
                    LEFT JOIN item_specific_guides isg ON gi.id = isg.item_id
                    WHERE gi.name = :t
                """), {"t": text}).fetchone()
                if res:
                    matched_item = {"id": res[0], "label": res[1], "name": res[2]}
                    if res[3]:
                        final_guide = res[3]
        except:
            pass

    # 2. 同义词模糊匹配（新增）
    if not matched_item and USE_MYSQL:
        matched_item = fuzzy_match_item(text)

    # 3. 数据库匹配成功
    if matched_item:
        lid = matched_item["id"]
        label = matched_item["label"]
        name = matched_item["name"]
        if not final_guide:
            final_guide = generate_guide(name, label)
        tokens, norms = get_attention_weights(text)
        return {
            "category": LABEL_MAP.get(label, "其他"),
            "confidence": 1.0,
            "method": "数据库同义词匹配",
            "related_links": get_related(name, label),
            "guide": final_guide,
            "tokens": tokens,
            "token_norms": norms
        }

    # 4. BERT 推理
    bert_lbl, bert_conf, is_anomaly = 8, 0.0, False
    tokens, norms = [], []
    if classifier:
        try:
            inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=32)
            with torch.no_grad():
                probs = torch.nn.functional.softmax(classifier(**inputs).logits, dim=-1)[0].numpy()
                top_idx = np.argmax(probs)
                bert_conf = float(probs[top_idx])
                bert_lbl = {0:1,1:2,2:4,3:8,4:16}.get(top_idx,8)
                is_anomaly = bert_conf < 0.65
            tokens, norms = get_attention_weights(text)
        except:
            pass

    # 5. 天行API兜底
    if bert_conf < 0.85:
        try:
            api_res = requests.get(f"https://apis.tianapi.com/lajifenlei/index?key={TIAN_API_KEY}&word={text}", timeout=2).json()
            if api_res.get("code") == 200:
                t = api_res["result"]["list"][0]
                api_lbl = {0:1,1:2,2:4,3:8}.get(t["type"],8)
                tokens, norms = get_attention_weights(text)
                return {
                    "category": LABEL_MAP[api_lbl],
                    "confidence": 0.99,
                    "method": "天行API纠偏",
                    "is_anomaly": False,
                    "guide": generate_guide(text, api_lbl),
                    "tokens": tokens,
                    "token_norms": norms
                }
        except:
            pass

    # 6. 生成模块化建议
    final_guide = generate_guide(text, bert_lbl)

    return {
        "category": LABEL_MAP.get(bert_lbl, "干垃圾"),
        "confidence": round(bert_conf,3),
        "method": "BERT语义引擎",
        "is_anomaly": is_anomaly,
        "related_links": get_related(text, bert_lbl),
        "guide": final_guide,
        "tokens": tokens,
        "token_norms": norms
    }

# ====================== 游戏题库接口 ======================
@app.get("/game_items")
async def get_game_items():
    try:
        if not USE_MYSQL or not engine:
            raise Exception("无数据库")
        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT name, label FROM garbage_items ORDER BY RAND() LIMIT 150")
            ).fetchall()
            return [{"name": r[0], "label": r[1]} for r in result]
    except:
        return [
            {"name": "塑料瓶", "label": 1},
            {"name": "电池", "label": 2},
            {"name": "苹果核", "label": 4}
        ]

# ====================== 游戏错题记录 ======================
class GameMistake(BaseModel):
    name: str
    wrong_label: int
    correct_label: int

@app.post("/log_game_mistake")
async def log_game_mistake(m: GameMistake):
    if not USE_MYSQL or not engine:
        return {"status": "skip"}
    try:
        # 使用 begin() 块，代码执行完会自动执行 COMMIT
        with engine.begin() as conn:
            query = sa.text("""
                INSERT INTO game_mistakes_stats 
                (item_name, correct_label, wrong_label, occurrence_count)
                VALUES (:name, :correct, :wrong, 1)
                ON DUPLICATE KEY UPDATE 
                occurrence_count = occurrence_count + 1
            """)
            conn.execute(query, {
                "name": m.name,
                "correct": m.correct_label,
                "wrong": m.wrong_label
            })
        logging.info(f"📊 数据库已实时更新错题: {m.name}")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"❌ 数据库更新失败: {e}")
        return {"status": "error"}

@app.get("/get_mistake_rank")
async def get_mistake_rank():
    if not USE_MYSQL or not engine:
        return []
    try:
        with engine.connect() as conn:
            res = conn.execute(sa.text("""
                SELECT item_name, wrong_label, occurrence_count
                FROM game_mistakes_stats
                ORDER BY occurrence_count DESC LIMIT 10
            """)).fetchall()
            return [{"name":r[0],"wrong":r[1],"count":r[2]} for r in res]
    except:
        return []
    
# ====================== 新增：智谱 AI 诊断接口 ======================
ZHIPU_API_KEY = "69c729c061af4cf590f6079d0ea1c1cb.J7RQE5IslWO6rnzT" 

class SessionMistake(BaseModel):
    item: str
    correct_label_name: str
    err_count: int

class SessionData(BaseModel):
    score: int
    accuracy: str
    mistakes: list[SessionMistake]

@app.post("/get_ai_analysis")
async def get_ai_analysis(data: SessionData):
    try:
        if not data.mistakes:
            prompt = f"用户刚刚完成了一局垃圾分类挑战，得分{data.score}，正确率{data.accuracy}。他这一局一个都没错！请以环保专家的身份写一段简短的、充满激情的表扬和进阶建议。"
        else:
            mistake_desc = "; ".join([f"物品【{m.item}】(应为{m.correct_label_name})错了{m.err_count}次" for m in data.mistakes])
            prompt = f"""
            你是一位专业的环保AI导师。用户刚刚完成了一局分类挑战：
            - 本局得分：{data.score}
            - 识别正确率：{data.accuracy}
            - 本局具体的错题：{mistake_desc}

            请根据“本局”的表现，不要说废话，直接完成以下任务：
            1. 毒辣地指出用户在本局中暴露的认知短板。
            2. 针对错题中的物品（如{data.mistakes[0].item}等），给出一个好记的分类冷知识。
            3. 用两到三句话激励他。
            字数控制在200字内，风格要极简、专业、现代，多使用Markdown加粗。
            """

        resp = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers={"Authorization": f"Bearer {ZHIPU_API_KEY}"},
            json={
                "model": "glm-4",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            },
            timeout=15
        ).json()
        
        return {"report": resp['choices'][0]['message']['content']}
    except Exception as e:
        return {"report": f"AI诊断模块暂时离线，请参考下方错题清单。({str(e)})"}

# ====================== 管理端纠正接口 ======================
class Correction(BaseModel):
    name: str
    correct_category: str

@app.post("/correct")
async def correct(c: Correction):
    try:
        if not USE_MYSQL or not engine:
            return {"ok": False, "error": "数据库未连接"}
        inv = {v:k for k,v in LABEL_MAP.items()}
        lbl = inv.get(c.correct_category)
        if not lbl:
            return {"ok": False, "error": "分类错误"}
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO garbage_items (name, label, synonyms)
                VALUES (:n,:l,:s)
                ON DUPLICATE KEY UPDATE label=VALUES(label)
            """), {"n":c.name,"l":lbl,"s":json.dumps([c.name], ensure_ascii=False)})
        return {"ok":True,"source":"人工纠正","new_confidence":1.0}
    except Exception as e:
        return {"ok":False,"error":str(e)}

if __name__ == "__main__":
    print("🚀 DeepVision 后端引擎启动中...")
    uvicorn.run(app, host="127.0.0.1", port=8000)