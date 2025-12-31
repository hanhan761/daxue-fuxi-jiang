# 🎓 大学复习酱 (Smart Review App) - v3.0

**大学复习酱** 是一个结合了 **AI 多智能体生成技术** 与 **科学复习方法** 的智能复习工具。

🚀 **v3.0 新特性**：新增 **费曼技巧智能出题 (Feynman Quiz Agent)**，不仅能帮你构建知识体系，还能像老师一样通过提问检验你的掌握程度！

---

## ✨ 核心功能

### 1. 🤖 AI 智能构建知识库
不再需要手动输入枯燥的知识点。只需上传你的复习资料，后端的 AI Agent 流水线会自动处理：
*   **多格式支持**：支持 PDF, PPT/PPTX, DOC/DOCX, TXT, MD 等多种格式。
*   **多智能体协作**：采用 Orchestrator 编排模式，包含预处理、整合、分类、解析、统一和合并 6 个阶段，确保知识点提取的准确性。
*   **结构化输出**：自动生成包含节点（知识点）和边（逻辑关系）的知识图谱。

### 2. 🧠 费曼技巧智能出题 (New!)
基于费曼学习法，AI 变身提问者：
*   **针对性提问**：输入你想复习的 Topic，AI 会生成考察理解深度的题目。
*   **主动式学习**：通过回答问题，强迫自己用自己的语言组织知识，发现盲区。

### 3. 📝 科学复习系统
*   **闪卡模式**：支持 "会/不太会/不会" 三种状态打分。
*   **智能队列**：根据艾宾浩斯记忆曲线和你的掌握程度，智能安排复习优先级。
*   **可视化统计**：内置 Chart.js 图表，直观展示 Top 15 难点知识。

---

## 🛠️ 技术栈

*   **前端**：原生 HTML5, CSS3, JavaScript (Vanilla ES6+), Chart.js
*   **后端**：Python 3.11, Flask
*   **AI 引擎**：DeepSeek API (兼容 OpenAI 格式)
*   **数据存储**：
    *   知识库 & 文本：LocalStorage
    *   图片资源：IndexedDB

---

## 🚀 快速开始

### 方式一：Windows 一键启动 (推荐)

如果你是 Windows 用户，可以直接使用根目录下的脚本：
1.  双击 `先点这个：一键安装环境.bat` 初始化环境。
2.  双击 `一键启动复习系统.bat` 启动应用。

### 方式二：手动安装与启动

#### 1. 环境准备
确保你的电脑上安装了 Python 3.8+ (推荐 3.11)。

#### 2. 安装依赖
在项目根目录下，安装 Python 依赖库：

```bash
# 使用 pip
pip install -r requirements.txt
# 或者手动安装核心库
pip install flask flask-cors python-dotenv requests
```

> **Conda 用户** 可以使用 `environment.yml` 创建环境：
> `conda env create -f environment.yml`

#### 3. 配置 API Key
项目需要 DeepSeek 的 API Key 才能运行。
1.  在项目根目录创建一个 `.env` 文件。
2.  添加以下内容（也可在前端界面动态输入）：

```env
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

#### 4. 启动服务
运行 `server.py` 启动后端服务。服务启动后会自动打开默认浏览器。

```bash
python server.py
```

*   **后端地址**：`http://127.0.0.1:5000`
*   **前端页面**：浏览器会自动弹出 `start.html`

---

## 💡 使用指南

### 🌟 生成知识库
1.  打开网页，点击主页的 **"✨ AI 生成知识库"**。
2.  输入知识库名称（例如：操作系统复习）。
3.  在 **"系统设置"** 中输入你的 DeepSeek API Token（如果在后端配置了可跳过）。
4.  拖拽上传你的复习资料（PDF/PPT/Word）。
5.  点击生成。请耐心等待，AI 需要几分钟时间阅读和构建图谱。

### 🎓 费曼技巧自测
1.  在复习界面选择一个知识点或直接进入 **"费曼模式"**（如果已集成）。
2.  输入你想测试的主题 (Topic)。
3.  AI 会生成一道题目，尝试口头或书面回答，检验自己是否真的“懂了”。

---

## 📂 项目结构

```text
Smart_Review_Generator/
├── 1_inputs/               # (参考) 示例输入文件
├── 2_outputs/              # AI 流水线生成的中间产物
│   └── 5_final/            # 最终生成的 JSON 位于此处
├── configs/
│   ├── settings.py         # 路径配置
│   └── agent_prompts.yaml  # AI 提示词配置
├── src/
│   ├── agent/              # 知识库生成智能体 (Preprocessor, Parser 等)
│   ├── feiman/             # 费曼技巧出题智能体 (Quiz Agent)
│   ├── utils/              # 工具函数 (Logger 等)
│   └── orchestrator.py     # AI 流水线总编排器
├── temp_uploads/           # [自动生成] 上传文件沙箱
├── logs/                   # 系统日志
├── app.js                  # 前端核心逻辑
├── style.css               # 前端样式
├── start.html              # 前端入口页面
├── server.py               # Flask 后端入口
└── .env                    # 环境变量配置文件
```

---

## ⚠️ 常见问题

**Q: 生成过程中报错 "Pipeline 执行返回失败状态"？**
A: 请检查 `logs/app.log` 或控制台输出。常见原因：
*   API Token 无效或余额不足。
*   上传的文件格式不受支持或文件损坏。
*   网络连接问题导致无法连接 DeepSeek API。

**Q: 费曼模式没有反应？**
A: 确保 `server.py` 正在运行，并且 API Token 有效。费曼模式依赖实时 AI 生成。

---

## 📜 许可证

MIT License
