import os
import math
import torch
import pandas as pd
import numpy as np
from difflib import SequenceMatcher


class FallbackRecognizer:
    """基于 BERT embedding 的开放集识别 + 回退字符串相似度识别。

    策略：
    1. 计算所有训练样本的 pooled embedding，按 label 计算类原型(prototype)。
    2. 推理时先与类原型比较（cosine），若相似度 >= prototype_threshold 则直接返回。
    3. 否则在所有训练样本 embedding 上做最近邻（cosine），若相似度 >= knn_threshold 则返回该样本标签。
    4. 再不行则用字符串相似度（difflib）在训练文本上匹配，若 ratio >= fuzzy_threshold 返回标签。
    5. 否则标记为未知（open-set），并返回最接近的候选与其相似度供参考。
    """

    def __init__(self, model, tokenizer, train_csv_path, device=None,
                 prototype_threshold=0.80, knn_threshold=0.65, fuzzy_threshold=0.70):
        self.model = model
        self.tokenizer = tokenizer
        self.train_csv_path = train_csv_path
        self.device = device or (torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu'))
        self.prototype_threshold = prototype_threshold
        self.knn_threshold = knn_threshold
        self.fuzzy_threshold = fuzzy_threshold

        self.model.to(self.device)
        self.model.eval()

        self._load_train_data_and_build_index()

    def _text_to_embedding(self, text):
        inputs = self.tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=40)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            # use the underlying bert model to get pooled output
            if hasattr(self.model, 'bert'):
                out = self.model.bert(**inputs)
                # some configs include pooler_output
                if hasattr(out, 'pooler_output') and out.pooler_output is not None:
                    emb = out.pooler_output
                else:
                    # fallback to first token ([CLS])
                    emb = out.last_hidden_state[:, 0, :]
            else:
                # fallback to using the classifier model's outputs if necessary
                out = self.model(**inputs, output_hidden_states=True, return_dict=True)
                emb = out.hidden_states[-1][:, 0, :]

        emb = emb.squeeze(0).cpu().numpy()
        # normalize to unit vector for cosine similarity
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb

    def _load_train_data_and_build_index(self):
        if not os.path.exists(self.train_csv_path):
            raise FileNotFoundError(self.train_csv_path)

        df = pd.read_csv(self.train_csv_path)
        # expect columns: name,label
        texts = df.iloc[:, 0].astype(str).tolist()
        labels = df.iloc[:, 1].astype(int).tolist()

        self.train_texts = texts
        self.train_labels = labels

        # compute embeddings for all training texts
        embs = []
        for t in texts:
            try:
                e = self._text_to_embedding(t)
            except Exception:
                # fallback empty vector
                e = np.zeros((self.model.config.hidden_size,), dtype=float)
            embs.append(e)

        self.train_embs = np.stack(embs, axis=0)

        # build prototypes per label (average of normalized embeddings)
        prototypes = {}
        for lbl in sorted(set(labels)):
            idxs = [i for i, l in enumerate(labels) if l == lbl]
            if len(idxs) == 0:
                continue
            proto = np.mean(self.train_embs[idxs], axis=0)
            norm = np.linalg.norm(proto)
            if norm > 0:
                proto = proto / norm
            prototypes[lbl] = proto

        self.prototypes = prototypes

    @staticmethod
    def _cosine_sim(a, b):
        # a: (d,), b: (n,d) or (d,)
        a = np.asarray(a)
        b = np.asarray(b)
        if b.ndim == 1:
            denom = (np.linalg.norm(a) * np.linalg.norm(b))
            return float(np.dot(a, b) / denom) if denom > 0 else 0.0
        dots = np.dot(b, a)
        denom = (np.linalg.norm(a) * np.linalg.norm(b, axis=1))
        denom = np.where(denom == 0, 1e-8, denom)
        return dots / denom

    def predict(self, text):
        emb = self._text_to_embedding(text)

        # 1) prototype similarity
        proto_sims = {lbl: float(np.dot(emb, proto)) for lbl, proto in self.prototypes.items()}
        if proto_sims:
            best_lbl = max(proto_sims, key=proto_sims.get)
            best_sim = proto_sims[best_lbl]
            if best_sim >= self.prototype_threshold:
                return {
                    'label_id': int(best_lbl),
                    'method': 'prototype',
                    'confidence': float(best_sim)
                }

        # 2) nearest neighbor in training embeddings
        sims = self._cosine_sim(emb, self.train_embs)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])
        best_label = int(self.train_labels[best_idx])
        if best_sim >= self.knn_threshold:
            return {
                'label_id': best_label,
                'method': 'knn',
                'confidence': best_sim,
                'matched_text': self.train_texts[best_idx]
            }

        # 3) fuzzy string match fallback
        ratios = [SequenceMatcher(None, text, t).ratio() for t in self.train_texts]
        best_f_idx = int(np.argmax(ratios))
        best_ratio = float(ratios[best_f_idx])
        best_f_label = int(self.train_labels[best_f_idx])
        if best_ratio >= self.fuzzy_threshold:
            return {
                'label_id': best_f_label,
                'method': 'fuzzy',
                'confidence': best_ratio,
                'matched_text': self.train_texts[best_f_idx]
            }

        # 4) unknown / open-set: return best candidate for reference
        return {
            'label_id': best_label,
            'method': 'unknown',
            'confidence': best_sim,
            'matched_text': self.train_texts[best_idx]
        }
