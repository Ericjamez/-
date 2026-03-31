import os
import json
import logging
import datetime
import numpy as np
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

LABEL_MAP = {
    1: "可回收物",
    2: "有害垃圾",
    4: "厨余垃圾",
    8: "其他垃圾",
    16: "大件垃圾"
}

LABEL_MAP_REVERSE = {v: k for k, v in LABEL_MAP.items()}

tokenizer = None
classifier = None
base_model = None

def init_bert_model(app):
    global tokenizer, classifier, base_model
    
    model_path = app.config.get('BERT_MODEL_PATH')
    if not model_path or not os.path.exists(model_path):
        logging.warning("BERT 模型路径未配置或不存在")
        return False
    
    try:
        from transformers import BertTokenizer, BertForSequenceClassification, BertModel
        
        tokenizer = BertTokenizer.from_pretrained(model_path)
        classifier = BertForSequenceClassification.from_pretrained(
            model_path,
            output_attentions=True,
            attn_implementation="eager"
        )
        base_model = BertModel.from_pretrained(model_path)
        classifier.eval()
        base_model.eval()
        logging.info("BERT 模型加载成功")
        return True
    except Exception as e:
        logging.error(f"BERT 模型加载失败: {e}")
        return False

@lru_cache(maxsize=512)
def get_embedding(text):
    global tokenizer, base_model
    if not base_model or not tokenizer:
        return np.zeros(768)
    try:
        import torch
        inputs = tokenizer(text, return_tensors='pt', truncation=True, padding=True, max_length=32)
        with torch.no_grad():
            out = base_model(**inputs)
        return out.last_hidden_state.mean(dim=1).squeeze().numpy()
    except:
        return np.zeros(768)

def get_related_items(text, label_value, db):
    try:
        target = get_embedding(text)
        from app.models import GarbageItem
        items = GarbageItem.query.filter_by(label=label_value).limit(50).all()
        sims = []
        for item in items:
            emb = get_embedding(item.name)
            score = np.dot(target, emb) / (np.linalg.norm(target) * np.linalg.norm(emb) + 1e-8)
            sims.append((item.name, score))
        sims.sort(key=lambda x: x[1], reverse=True)
        return [x[0] for x in sims[1:4]]
    except:
        return []

def fuzzy_match_item(text, db):
    try:
        from rapidfuzz import fuzz
        from app.models import GarbageItem
        items = GarbageItem.query.all()
        candidates = []
        for item in items:
            cname = item.name.strip()
            syns = json.loads(item.synonyms) if item.synonyms else []
            all_names = [cname] + syns
            for n in all_names:
                score = fuzz.ratio(text.lower(), n.lower())
                if score > 75:
                    candidates.append((item, score))
                    break
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1], reverse=True)
        best = candidates[0][0]
        return {"id": best.id, "name": best.name, "label": best.label}
    except:
        return None

def generate_guide(item_name, label, db):
    try:
        from app.models import GuideComponent
        components = GuideComponent.query.filter_by(category_label=label).order_by(GuideComponent.priority.desc()).all()
        parts = []
        for c in components:
            txt = c.text_template.replace("{item}", item_name)
            parts.append(txt)
        if parts:
            return "；".join(parts) + "。"
    except:
        return None
    return None

def get_attention_weights(text):
    global tokenizer, classifier
    if not tokenizer or not classifier:
        return [], []
    try:
        import torch
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=32)
        with torch.no_grad():
            outputs = classifier(**inputs, output_attentions=True)
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])
        attn = outputs.attentions[-1][0].mean(dim=0).mean(dim=0).numpy()
        attn = (attn - attn.min()) / (attn.max() - attn.min() + 1e-8)
        return tokens, attn.tolist()
    except:
        return [], []

def predict_garbage(text, db, tian_api_key=None):
    from app.models import GarbageItem, ItemSpecificGuide
    
    text = text.strip()
    if not text:
        return {"category": "未知", "confidence": 0}
    
    final_guide = None
    matched_item = None
    
    try:
        res = db.session.execute(
            db.text("""
                SELECT gi.id, gi.label, gi.name, isg.full_guide
                FROM garbage_items gi
                LEFT JOIN item_specific_guides isg ON gi.id = isg.item_id
                WHERE gi.name = :t
            """), {"t": text}
        ).fetchone()
        if res:
            matched_item = {"id": res[0], "label": res[1], "name": res[2]}
            if res[3]:
                final_guide = res[3]
    except:
        pass
    
    if not matched_item:
        matched_item = fuzzy_match_item(text, db)
    
    if matched_item:
        label = matched_item["label"]
        name = matched_item["name"]
        if not final_guide:
            final_guide = generate_guide(name, label, db)
        tokens, norms = get_attention_weights(text)
        return {
            "category": LABEL_MAP.get(label, "其他垃圾"),
            "confidence": 1.0,
            "method": "数据库匹配",
            "related_links": get_related_items(name, label, db),
            "guide": final_guide,
            "tokens": tokens,
            "token_norms": norms
        }
    
    bert_lbl, bert_conf, is_anomaly = 8, 0.0, False
    tokens, norms = [], []
    
    global classifier, tokenizer
    if classifier and tokenizer:
        try:
            import torch
            inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=32)
            with torch.no_grad():
                probs = torch.nn.functional.softmax(classifier(**inputs).logits, dim=-1)[0].numpy()
                top_idx = np.argmax(probs)
                bert_conf = float(probs[top_idx])
                bert_lbl = {0: 1, 1: 2, 2: 4, 3: 8, 4: 16}.get(top_idx, 8)
                is_anomaly = bert_conf < 0.65
            tokens, norms = get_attention_weights(text)
        except:
            pass
    
    if tian_api_key and bert_conf < 0.85:
        try:
            import requests
            api_res = requests.get(
                f"https://apis.tianapi.com/lajifenlei/index?key={tian_api_key}&word={text}",
                timeout=2
            ).json()
            if api_res.get("code") == 200:
                t = api_res["result"]["list"][0]
                api_lbl = {0: 1, 1: 2, 2: 4, 3: 8}.get(t["type"], 8)
                tokens, norms = get_attention_weights(text)
                return {
                    "category": LABEL_MAP[api_lbl],
                    "confidence": 0.99,
                    "method": "天行API纠偏",
                    "is_anomaly": False,
                    "guide": generate_guide(text, api_lbl, db),
                    "tokens": tokens,
                    "token_norms": norms
                }
        except:
            pass
    
    final_guide = generate_guide(text, bert_lbl, db)
    
    return {
        "category": LABEL_MAP.get(bert_lbl, "其他垃圾"),
        "confidence": round(bert_conf, 3),
        "method": "BERT语义引擎",
        "is_anomaly": is_anomaly,
        "related_links": get_related_items(text, bert_lbl, db),
        "guide": final_guide,
        "tokens": tokens,
        "token_norms": norms
    }

def get_ai_game_analysis(score, accuracy, mistakes, ZHIPU_API_KEY):
    try:
        import requests
        
        if not mistakes:
            prompt = f"用户刚刚完成了一局垃圾分类挑战，得分{score}，正确率{accuracy}。他这一局一个都没错！请以环保专家的身份写一段简短的、充满激情的表扬和进阶建议。"
        else:
            mistake_desc = "; ".join([f"物品【{m['item']}】(应为{m['correct_label_name']})错了{m['err_count']}次" for m in mistakes])
            prompt = f"""
                你是一位专业的环保AI导师。用户刚刚完成了一局分类挑战：
                - 本局得分：{score}
                - 识别正确率：{accuracy}
                - 本局具体的错题：{mistake_desc}

                请根据"本局"的表现，不要说废话，直接完成以下任务：
                1. 毒辣地指出用户在本局中暴露的认知短板。
                2. 针对错题中的物品，给出一个好记的分类冷知识。
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
        return {"report": f"AI诊断模块暂时离线。({str(e)})"}

def predict_flow():
    now = datetime.datetime.now()
    labels = [(now + datetime.timedelta(hours=i)).strftime("%H:00") for i in range(24)]
    data = [round(30 * np.sin(i/3.8) + 50 + float(np.random.normal(0, 3)), 2) for i in range(24)]
    return {"labels": labels, "data": data}
