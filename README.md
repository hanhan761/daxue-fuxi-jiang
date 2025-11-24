🎓 大学复习酱 (Smart Review App) - v3.0 AI Integration

大学复习酱 是一个结合了 AI 多智能体生成技术 与 科学复习方法 的智能复习工具。

它不再需要你手动输入枯燥的知识点。只需上传你的复习资料（PDF, PPT, Word, TXT），后端的 AI Agent 流水线会自动分析、提取、分类并生成结构化的知识图谱。前端界面提供闪卡复习、艾宾浩斯记忆曲线追踪以及详细的数据统计。

✨ 主要功能

🤖 AI 智能构建

多格式支持：支持上传 PDF, PPT/PPTX, DOC/DOCX, TXT, MD 等多种格式。

多智能体流水线：后端采用 Orchestrator 编排模式，包含预处理、整合、分类、解析、统一和合并 6 个阶段，确保知识点提取的准确性。

任务隔离：支持并发生成，每个生成任务在独立的沙箱目录中处理，互不干扰。

🧠 智能复习系统

知识图谱可视化：生成的知识库包含节点（知识点）和边（逻辑关系）。

闪卡模式：支持 "会/不太会/不会" 三种状态打分。

智能队列：根据你的掌握程度（"不会"的次数或比例）智能安排复习优先级。

📊 数据统计与管理

可视化图表：内置 Chart.js 图表，展示 Top 15 难点知识。

本地存储：所有数据（包括图片）存储在浏览器的 IndexedDB 和 LocalStorage 中，保护隐私。

导入/导出：支持将生成的知识库导出为 JSON 分享，或导入他人的知识库。

🛠️ 技术栈

前端：原生 HTML5, CSS3, JavaScript (Vanilla ES6+), Chart.js

后端：Python 3.x, Flask, Werkzeug

AI 引擎：DeepSeek API (兼容 OpenAI 格式)

数据存储：Browser IndexedDB (图片), LocalStorage (文本数据)

🚀 快速开始

1. 环境准备

确保你的电脑上安装了 Python 3.8+。

2. 安装依赖

在项目根目录下，安装 Python 依赖库：

pip install flask flask-cors python-dotenv requests


(注：如果你的项目中还有其他特定的依赖（如 PDF 解析库），请一并安装)

3. 配置 API Key

项目需要 DeepSeek 的 API Key 才能运行。

在项目根目录创建一个 .env 文件。

添加以下内容（虽然前端也可以动态输入 Token，但建议在后端配置默认值）：

DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_BASE_URL=[https://api.deepseek.com](https://api.deepseek.com)


4. 启动服务

运行 server.py 启动后端服务。服务启动后会自动打开默认浏览器。

python server.py


后端地址：http://127.0.0.1:5000

前端页面：通常会自动弹出，或访问 file://.../start.html (前端通过 CORS 访问后端)

📂 项目结构

Smart_Review_Generator/
├── 1_inputs/               # (默认) 输入文件目录
├── 2_outputs/              # AI 流水线生成的中间产物和最终结果
│   ├── 1_preprocessed/
│   ├── ...
│   └── 5_final/            # 最终生成的 JSON 位于此处
├── configs/
│   ├── settings.py         # 路径配置与环境设置
│   └── agent_prompts.yaml  # AI 提示词配置
├── src/
│   ├── agent/              # 各个 AI 智能体 (Preprocessor, Parser 等)
│   ├── utils/              # 工具函数 (Logger 等)
│   └── orchestrator.py     # AI 流水线总编排器
├── temp_uploads/           # [自动生成] 用于存放上传文件的临时沙箱目录
├── logs/                   # 系统日志
├── app.js                  # 前端核心逻辑
├── style.css               # 前端样式
├── start.html              # 前端入口页面
├── server.py               # Flask 后端入口
└── .env                    # 环境变量配置文件


💡 使用指南

启动应用：运行 server.py。

设置 Token：

在网页左侧菜单点击 "系统设置"。

输入你的 DeepSeek API Token 并保存。

生成知识库：

回到主页，点击 "✨ AI 生成知识库"。

输入知识库名称（例如：操作系统复习）。

拖拽上传你的复习资料（PDF/PPT/Word）。

点击生成。请耐心等待，AI 需要几分钟时间阅读和构建图谱。

开始复习：生成完成后，点击卡片进入详情页，开始你的复习之旅！

⚠️ 常见问题

Q: 生成过程中报错 "Pipeline 执行返回失败状态"？
A: 请检查 logs/app.log 或控制台输出。常见原因包括：

API Token 无效或余额不足。

上传的文件格式不受支持或文件损坏。

网络连接问题导致无法连接 DeepSeek API。

Q: 如何清理缓存文件？
A: 系统会自动清理 temp_uploads 中的临时文件。2_outputs 文件夹中的中间产物会在每次新任务开始时自动清理（除了预处理缓存）。

📜 许可证

MIT License