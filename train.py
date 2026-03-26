import os
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from transformers import BertTokenizer, BertForSequenceClassification

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

LABEL_MAP = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}  # 映射到连续索引 0-4
NUM_LABELS = 5

class GarbageDataset(Dataset):
    def __init__(self, csv_file, tokenizer_name='bert-base-chinese'):
        self.data = pd.read_csv(csv_file)
        self.tokenizer = BertTokenizer.from_pretrained(tokenizer_name)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        text = str(self.data.iloc[idx, 0])
        label_raw = int(self.data.iloc[idx, 1])
        label = LABEL_MAP.get(label_raw, 3)  # 默认干垃圾

        encoding = self.tokenizer(
            text,
            padding='max_length',
            truncation=True,
            max_length=20,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'labels': torch.tensor(label, dtype=torch.long)
        }

def train():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"--- 使用设备: {device} ---")

    model_name = 'bert-base-chinese'
    tokenizer = BertTokenizer.from_pretrained(model_name)
    model = BertForSequenceClassification.from_pretrained(model_name, num_labels=NUM_LABELS)
    model.to(device)

    dataset = GarbageDataset('train_data.csv')
    loader = DataLoader(dataset, batch_size=32, shuffle=True)
    optimizer = AdamW(model.parameters(), lr=2e-5)

    epochs = 5
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        correct = 0

        for batch in loader:
            optimizer.zero_grad()
            input_ids = batch['input_ids'].to(device)
            mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            outputs = model(input_ids, attention_mask=mask, labels=labels)
            loss = outputs.loss
            logits = outputs.logits
            preds = torch.argmax(logits, dim=-1)
            correct += torch.sum(preds == labels)

            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        acc = correct.double() / len(dataset)
        print(f"Epoch {epoch+1} | Loss: {total_loss/len(loader):.4f} | Acc: {acc:.2%}")

    save_path = "./my_garbage_model"
    model.save_pretrained(save_path)
    tokenizer.save_pretrained(save_path)
    # 保存标签映射
    import json
    with open(os.path.join(save_path, "label_map.json"), "w", encoding="utf-8") as f:
        json.dump({v: k for k, v in LABEL_MAP.items()}, f, ensure_ascii=False)
    print("✅ 模型训练完成，已保存到 my_garbage_model")

if __name__ == "__main__":
    train()