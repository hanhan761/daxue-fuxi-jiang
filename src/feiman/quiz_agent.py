import os
import sys
import json
from openai import OpenAI
import logging

# --- 1. 环境路径配置 ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# --- 2. 容错导入配置与 Logger ---
try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError as e:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    print(f"⚠️ [Init Warning] 无法导入 settings 或 logger: {e}")


    # [修复] 定义保底配置
    class Settings:
        DEEPSEEK_BASE_URL = "https://api.deepseek.com"
        AGENT_QUIZ_MODEL = "deepseek-chat"
        SMART_MODEL_NAME = "deepseek-chat"
        DEEPSEEK_API_KEY = None


    settings = Settings()

# --- 3. 导入业务逻辑 (Smart Flow) ---
try:
    # 确保 src/feiman/smart_flow/__init__.py 存在！
    from src.feiman.smart_flow.pipeline import run_smart_quiz_pipeline
except ImportError as e:
    logger.error(f"❌ 严重错误: 无法导入 smart_flow 模块。请检查 src/feiman/smart_flow/__init__.py 是否存在。详情: {e}")
    run_smart_quiz_pipeline = None

# ... (保留原有的 get_api_client 函数) ...
def get_api_client():
    # ... (代码保持不变，直接复制原来的即可) ...
    try:
        current_api_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", "")
        if not current_api_key: return None
        return OpenAI(
            api_key=current_api_key,
            base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
    except:
        return None


# ... (保留 run_quiz_generation 签名) ...

def run_quiz_generation(topic_input: str):
    logger.info(f"--- 启动: Smart Review 多智能体出题系统 (Topic: {topic_input}) ---")

    # 1. 获取客户端
    client = get_api_client()
    if not client:
        logger.error("无法启动：客户端初始化失败。")
        return None

    # 2. 获取模型配置 (优先使用 Smart Model)
    model_name = getattr(settings, "SMART_MODEL_NAME", getattr(settings, "AGENT_QUIZ_MODEL", "deepseek-chat"))

    # 3. 调用新的多智能体流水线
    # 这里不再实例化旧的 QuizAgent，而是直接运行 Pipeline
    try:
        result = run_smart_quiz_pipeline(client, topic_input, model_name)

        if result:
            logger.info("🎉 生成成功！")
            return result
        else:
            logger.error("生成失败，返回空结果。")
            return None

    except Exception as e:
        logger.error(f"流水线执行异常: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # 测试
    res = run_quiz_generation("相对论的时间膨胀效应")
    print(json.dumps(res, indent=2, ensure_ascii=False))