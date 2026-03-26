import os
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from torchvision import transforms, models
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
import ssl
ssl._create_default_https_context = ssl._create_unverified_context # 强制解决SSL下载报错

# ===================== 标签映射 =====================
def get_label_map(txt_path):
    class_names = []
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f.readlines():
            class_names.append(line.strip())

    label_map = {}
    for idx, name in enumerate(class_names):
        if '厨余' in name:
            label_map[idx] = 0
        elif '可回收' in name:
            label_map[idx] = 1
        elif '有害' in name:
            label_map[idx] = 2
        else:
            label_map[idx] = 3

    class_list = ['厨余垃圾', '可回收物', '有害垃圾', '其他垃圾']
    return label_map, class_list

# ===================== 数据集 =====================
class TrashDataset(Dataset):
    def __init__(self, root_dir, txt_path, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.img_paths = []
        self.labels = []

        self.label_map, self.class_list = get_label_map(txt_path)

        for sub_dir in range(265):
            sub_path = os.path.join(root_dir, str(sub_dir))
            if not os.path.exists(sub_path):
                continue

            for img_name in os.listdir(sub_path):
                if img_name.endswith(('jpg', 'png', 'jpeg')):
                    self.img_paths.append(os.path.join(sub_path, img_name))
                    self.labels.append(self.label_map[sub_dir])

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx):
        img = Image.open(self.img_paths[idx]).convert('RGB')
        label = self.labels[idx]
        if self.transform:
            img = self.transform(img)
        return img, label

# ===================== 路径 =====================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

train_dir = r"I:\Work\new\Waste_Sorting\dataset\train"
val_dir = r"I:\Work\new\Waste_Sorting\dataset\val"
test_dir = r"I:\Work\new\Waste_Sorting\dataset\test"
txt_path = r"I:\Work\new\Waste_Sorting\dataset\classname.txt"

batch_size = 16
epochs = 5
lr = 0.0001
num_classes = 4

# ===================== 预处理 =====================
train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

val_test_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# ===================== 加载数据 =====================
train_dataset = TrashDataset(train_dir, txt_path, train_transform)
val_dataset = TrashDataset(val_dir, txt_path, val_test_transform)
test_dataset = TrashDataset(test_dir, txt_path, val_test_transform)

train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

# ===================== ✅ 开启预训练权重（准确率暴涨） =====================
# ✔✔✔ 这是你准确率低的根本原因！现在打开！
model = models.resnet50(weights="IMAGENET1K_V1")

# 不冻结，全部训练（效果最好）
for param in model.parameters():
    param.requires_grad = True

# 替换最后一层
in_features = model.fc.in_features
model.fc = nn.Linear(in_features, num_classes)
model = model.to(device)

# ===================== 优化器 =====================
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=lr)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.5)

# ===================== 训练 =====================
best_acc = 0.0
for epoch in range(epochs):
    print(f"\nEpoch {epoch+1}/{epochs}")
    print('-'*30)

    model.train()
    train_loss, correct, total = 0.0, 0, 0
    for imgs, labels in tqdm(train_loader, desc='训练'):
        imgs, labels = imgs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        _, pred = torch.max(outputs, 1)
        correct += (pred == labels).sum().item()
        total += labels.size(0)

    train_acc = correct / total

    model.eval()
    val_correct, val_total = 0, 0
    with torch.no_grad():
        for imgs, labels in tqdm(val_loader, desc='验证'):
            imgs, labels = imgs.to(device), labels.to(device)
            outputs = model(imgs)
            _, pred = torch.max(outputs, 1)
            val_correct += (pred == labels).sum().item()
            val_total += labels.size(0)

    val_acc = val_correct / val_total
    print(f"训练 Acc: {train_acc:.4f} | 验证 Acc: {val_acc:.4f}")

    if val_acc > best_acc:
        best_acc = val_acc
        torch.save(model.state_dict(), "best_trash_4class.pth")
        print("✅ 最优模型已保存")

# ===================== 测试集 =====================
print("\n🧪 测试集评估...")
model.load_state_dict(torch.load("best_trash_4class.pth", map_location=device, weights_only=True))
model.eval()

test_correct = 0
test_total = 0
with torch.no_grad():
    for imgs, labels in tqdm(test_loader, desc='测试'):
        imgs, labels = imgs.to(device), labels.to(device)
        outputs = model(imgs)
        _, pred = torch.max(outputs, 1)
        test_correct += (pred == labels).sum().item()
        test_total += labels.size(0)

test_acc = test_correct / test_total
print(f"\n🎉 测试集准确率: {test_acc:.4f}")