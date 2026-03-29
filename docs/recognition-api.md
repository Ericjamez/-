# Recognition.html 页面文档

## 页面概述

`recognition.html` 是垃圾图片分类系统的核心识别页面，提供图片上传和相机拍照两种方式进行垃圾识别。

---

## 核心功能模块

### 1. 模式切换
- **上传模式 (upload)**: 用户上传本地图片进行识别
- **相机模式 (camera)**: 用户使用设备相机拍照识别

### 2. 图片上传功能
- 支持点击上传区域选择文件
- 支持拖拽上传
- 图片大小限制: 5MB
- 支持格式: 图片类型 (image/*)

### 3. 相机拍照功能
- 请求设备相机权限
- 支持前后摄像头 (优先后置)
- 拍照后自动转换为 JPEG 格式

### 4. 图片识别功能
- 发送图片到后端进行 AI 识别
- 显示识别结果: 分类、置信度、耗时
- 显示相关知识内容

### 5. 反馈功能
- 用户可提交识别错误的反馈
- 选择正确的垃圾分类
- 添加备注信息

---

## API 接口

### 1. 图片识别接口

**接口地址**: `POST /recognize`

**请求方式**: `FormData`

**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| image | File | 是 | 要识别的图片文件 |
| record_id | string | 否 | 已有的识别记录ID (用于重新识别) |

**调用示例**:
```javascript
const formData = new FormData();
formData.append('image', selectedImage);
if (currentRecordId) {
    formData.append('record_id', currentRecordId);
}

const response = await fetch('/recognize', {
    method: 'POST',
    body: formData
});

const data = await response.json();
```

**响应数据**:
```json
{
    "success": true,
    "result": {
        "category": "厨余垃圾",
        "confidence": 0.95,
        "time": 1.23,
        "record_id": 123
    },
    "knowledge": "厨余垃圾是指..."
}
```

---

### 2. 确认识别结果接口

**接口地址**: `POST /confirm-recognition/<record_id>`

**请求方式**: `POST`

**请求参数**: 无

**调用示例**:
```javascript
await fetch(`/confirm-recognition/${currentRecordId}`, {
    method: 'POST'
});
```

**响应数据**:
```json
{
    "success": true,
    "message": "识别结果已确认"
}
```

**使用场景**:
- 切换图片时确认上一张图片的识别结果
- 关闭页面时通过 `sendBeacon` 确认结果
- 删除图片时确认结果

---

### 3. 提交反馈接口

**接口地址**: `POST /submit-feedback`

**请求方式**: `FormData`

**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| real_category | string | 是 | 正确的垃圾分类 |
| note | string | 否 | 备注信息 |
| garbage_name | string | 否 | 垃圾名称 |
| wrong_category | string | 否 | 错误的分类 (识别结果) |
| confidence | string | 否 | 识别置信度 |
| record_id | string | 否 | 识别记录ID |
| image | File | 否 | 图片文件 |

**调用示例**:
```javascript
const formData = new FormData();
formData.append('real_category', realCategory);
formData.append('note', note);
formData.append('garbage_name', garbageName);
formData.append('wrong_category', resultCategory);
formData.append('confidence', resultConfidence);
if (currentRecordId) {
    formData.append('record_id', currentRecordId);
}
if (selectedImage) {
    formData.append('image', selectedImage);
}

const response = await fetch('/submit-feedback', {
    method: 'POST',
    body: formData
});

const data = await response.json();
```

**响应数据**:
```json
{
    "success": true,
    "message": "反馈提交成功"
}
```

---

## JavaScript 函数说明

### 模式切换函数

```javascript
function switchMode(mode)
```
- **参数**: `mode` - 'upload' 或 'camera'
- **功能**: 切换上传/相机模式，重置状态

### 图片处理函数

```javascript
function getImageId(file)
```
- **参数**: `file` - 文件对象
- **返回**: 唯一标识字符串
- **功能**: 生成图片唯一标识，用于判断是否为同一张图片

```javascript
function removeImage()
```
- **功能**: 移除已上传的图片，重置状态

### 相机控制函数

```javascript
async function startCamera()
```
- **功能**: 启动相机，请求权限

```javascript
function takePhoto()
```
- **功能**: 拍照并保存为图片文件

```javascript
function stopCamera()
```
- **功能**: 停止相机，释放资源

### 识别相关函数

```javascript
async function recognizeImage()
```
- **功能**: 发送图片进行识别，显示结果

```javascript
async function confirmPreviousRecognition()
```
- **功能**: 确认上一张图片的识别结果

```javascript
async function resetRecognition()
```
- **功能**: 重置识别状态，隐藏结果

### 反馈相关函数

```javascript
function feedback()
```
- **功能**: 打开反馈弹窗

```javascript
function closeFeedback()
```
- **功能**: 关闭反馈弹窗

```javascript
async function submitFeedback()
```
- **功能**: 提交反馈信息

---

## 全局变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| currentMode | string | 当前模式 ('upload' 或 'camera') |
| selectedImage | File | 当前选中的图片文件 |
| currentRecordId | number | 当前识别记录ID |
| lastRecognizedImageId | string | 上次识别的图片ID |
| hasRecognized | boolean | 是否已识别 |
| cameraStream | MediaStream | 相机流对象 |

---

## 事件监听

### 文件上传事件
```javascript
document.getElementById('image-upload').addEventListener('change', function(e) {...})
```

### 拖拽上传事件
```javascript
uploadArea.addEventListener('dragover', function(e) {...})
uploadArea.addEventListener('dragleave', function() {...})
uploadArea.addEventListener('drop', function(e) {...})
```

### 页面卸载事件
```javascript
window.addEventListener('beforeunload', function() {...})
```

### 模态框点击事件
```javascript
document.getElementById('feedback-modal').addEventListener('click', function(e) {...})
```

---

## UI 组件

### 1. 标签页切换
- `.tab` - 标签按钮
- `.tab.active` - 激活状态

### 2. 上传区域
- `.upload-area` - 上传区域容器
- `#upload-preview` - 上传提示区域
- `#image-preview` - 图片预览区域

### 3. 相机区域
- `#camera` - 视频元素
- `#camera-preview` - Canvas 预览
- `#camera-placeholder` - 相机占位符

### 4. 识别结果
- `#recognition-result` - 结果容器
- `#result-category` - 分类结果
- `#result-confidence` - 置信度
- `#result-time` - 识别耗时
- `#knowledge-content` - 知识内容

### 5. 反馈弹窗
- `#feedback-modal` - 弹窗容器
- `#real-category` - 分类选择
- `#garbage-name` - 垃圾名称
- `#feedback-note` - 备注输入

---

## 样式类说明

| 类名 | 说明 |
|------|------|
| `.highlight` | 结果高亮显示 |
| `.has-result` | 有识别结果时的布局类 |
| `.active` | 激活状态 |
| `.success-alert` | 成功提示 |
| `.alert-success` | 成功警告框 |
| `.alert-error` | 错误警告框 |

---

## 注意事项

1. **图片大小限制**: 5MB
2. **相机权限**: 需要用户授权
3. **识别确认**: 切换图片或关闭页面前会自动确认上一张图片的识别结果
4. **反馈提交**: 提交反馈后会重置识别状态
