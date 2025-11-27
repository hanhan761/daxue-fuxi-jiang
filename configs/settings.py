import os
from pathlib import Path
from dotenv import load_dotenv  # 用于安全加载 .env 文件中的 API 密钥
import datetime
import sys

# --- 1. 安全加载 .env 文件 ---
# (这会加载项目根目录下的 .env 文件)
load_dotenv()

# --- 2. 核心路径定义 ---
# (此 settings.py 文件位于 'configs/' 目录中)
# BASE_DIR 指向项目根目录 (Smart_Review_Generator/)
try:
    BASE_DIR = Path(__file__).resolve().parent.parent
except NameError:
    # 兼容某些情况（例如VSCode的Python REPL）
    BASE_DIR = Path(os.getcwd())

# [兼容性补充] server.py 中使用了 PROJECT_ROOT，将其指向 BASE_DIR
PROJECT_ROOT = BASE_DIR

# 将项目根目录添加到 sys.path (这有助于解决 import 问题)
sys.path.append(str(BASE_DIR))


# --- 输入路径 ---
INPUTS_DIR = BASE_DIR / "1_inputs"
# [兼容性补充] 临时上传目录 (server.py 会用到)
TEMP_DIR = BASE_DIR / "temp_uploads"

# --- 输出路径 (与 agents 编号对应) ---
OUTPUT_DIR = BASE_DIR / "2_outputs"

# [兼容性补充] 确保 server.py 能找到最终图谱
# server.py 读取路径为: settings.OUTPUT_GRAPH / 'final_graph.json'
OUTPUT_GRAPH = BASE_DIR / "2_outputs"

OUTPUT_PREPROCESSED = OUTPUT_DIR / "1_preprocessed"  # 对应 1_preprocessor
OUTPUT_INTEGRATED = OUTPUT_DIR / "2_integrated"     # 对应 2_integrator
OUTPUT_CLASSIFIED = OUTPUT_DIR / "3_classified"     # 对应 3_classifier
OUTPUT_PARSED = OUTPUT_DIR / "4_parsed"           # 对应 4_parser
# ⬇️ 1. 【V4.5 升级：添加新路径】 ⬇️
OUTPUT_UNIFIED = OUTPUT_DIR / "4.5_unified"        # 对应 4.5_unifier

# ⬇️ V5.5 [新增] 给绘图师分配的目录
OUTPUT_GRAPH_EDGES = OUTPUT_DIR / "5.5_graph_edges"

OUTPUT_FINAL = OUTPUT_DIR / "5_final"            # 对应 5_merger (现在是第6步)

# --- 配置和日志路径 ---
CONFIGS_DIR = BASE_DIR / "configs"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
PROMPTS_FILE = CONFIGS_DIR / "agent_prompts.yaml"
# (为 formula_renderer.py 添加字体路径)
FONT_PATH = CONFIGS_DIR / "fonts" / "simhei.ttf"


# --- 3. 智能体 API 配置 ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "YOUR_API_KEY_HERE")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

if DEEPSEEK_API_KEY == "YOUR_API_KEY_HERE":
    print("=" * 50)
    print("警告：未在 .env 文件中检测到 'DEEPSEEK_API_KEY'。")
    print("请在项目根目录创建 .env 文件并设置您的 API 密钥。")
    print("=" * 50)

# --- 4. 智能体模型名称配置 ---
AGENT_CLASSIFIER_MODEL = "deepseek-chat"
AGENT_PARSER_MODEL_DEF = "deepseek-chat"
AGENT_PARSER_MODEL_FORMULA = "deepseek-chat"
# ⬇️ 2. 【V4.5 升级：添加新模型】 ⬇️
AGENT_UNIFIER_MODEL = "deepseek-chat" # (推荐使用更强的模型，例如 deepseek-coder)

# --- 5. 性能配置 ---
# ⬇️ 3. 【V4.5 升级：添加并发设置】 ⬇️
# (用于 4_parser 和 4.5_unifier)
PARSER_MAX_WORKERS = 1 

# --- 6. 最终产物配置 ---
# (原第5节)
FINAL_KB_NAME = "自动生成的Smart Review知识库"


# --- 7. 辅助函数 (供 orchestrator.py 调用) ---
# (原第6节)
def setup_directories():
    """
    在流水线开始时，一次性创建所有必需的目录。
    """
    print("Setting up directory structure...")
    dirs_to_create = [
        INPUTS_DIR,          # 确保输入目录存在
        TEMP_DIR,            # [新增] 确保临时上传目录存在，否则 server.py 保存文件会报错
        OUTPUT_PREPROCESSED,
        OUTPUT_INTEGRATED,
        OUTPUT_CLASSIFIED,
        OUTPUT_PARSED,
        # ⬇️ 4. 【V4.5 升级：添加新目录到创建列表】 ⬇️
        OUTPUT_UNIFIED,
        # ⬇️ 4. 【V5.5 升级：绘图师输出文件】 ⬇️
        OUTPUT_GRAPH_EDGES,
        OUTPUT_FINAL,
        LOG_DIR
    ]

    for dir_path in dirs_to_create:
        # exist_ok=True 意味着如果目录已存在，也不会报错
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            print(f"警告：无法创建目录 {dir_path}: {e}")

    # (可选) 创建一个空的日志文件
    if not os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"Log file created at {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n\n")
        except Exception as e:
            print(f"警告：无法创建日志文件 {LOG_FILE}: {e}")

    print("...Directory setup complete.")


# --- 8. (可选) 独立运行测试 ---
# (原第7节)
if __name__ == "__main__":
    print("--- (独立运行 settings.py 进行测试) ---")
    print(f"项目根目录 (BASE_DIR): {BASE_DIR}")
    print(f"兼容根目录 (PROJECT_ROOT): {PROJECT_ROOT}")
    print(f"输入目录 (INPUTS_DIR): {INPUTS_DIR}")
    print(f"临时目录 (TEMP_DIR): {TEMP_DIR}")
    print(f"解析后目录 (OUTPUT_PARSED): {OUTPUT_PARSED}")
    print(f"统一后目录 (OUTPUT_UNIFIED): {OUTPUT_UNIFIED}") # (新)
    print(f"最终输出目录 (OUTPUT_FINAL): {OUTPUT_FINAL}")
    print(f"Prompts 文件路径 (PROMPTS_FILE): {PROMPTS_FILE}")
    print(f"DeepSeek API 密钥 (前4位): {DEEPSEEK_API_KEY[:4]}...")
    print("\n正在测试创建目录...")
    setup_directories()
    print("--- (测试完毕) ---")