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
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ [Init Warning] 无法导入 settings 或 logger: {e}")


    class Settings:
        DEEPSEEK_BASE_URL = "https://api.deepseek.com"
        AGENT_QUIZ_MODEL = "deepseek-chat"
        DEEPSEEK_API_KEY = None


    settings = Settings()

# --- 3. 导入业务逻辑 (Smart Flow) ---
try:
    from src.feiman.smart_flow.pipeline import run_smart_quiz_pipeline
except ImportError as e:
    logger.error(f"❌ 严重错误: 无法导入 smart_flow 模块。详情: {e}")
    run_smart_quiz_pipeline = None


# --- 4. 核心鉴权逻辑 ---
def get_api_client():
    """初始化 API 客户端"""
    try:
        current_api_key = os.environ.get("DEEPSEEK_API_KEY")
        source = "环境变量 (os.environ)"

        if not current_api_key:
            current_api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
            source = "配置文件 (settings)"

        if not current_api_key:
            logger.error("CRITICAL: 未检测到 API Key。")
            return None

        logger.info(f"[DEBUG] API 客户端初始化中... 来源: {source}")

        client = OpenAI(
            api_key=current_api_key,
            base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        return client
    except Exception as e:
        logger.error(f"Error: 初始化客户端失败: {e}", exc_info=True)
        return None


# --- 5. 运行入口 (统一使用 deepseek-chat) ---
def run_quiz_generation(topic_input):
    """
    执行智能出题流程。
    """
    # 解析输入
    title = ""
    content = ""

    if isinstance(topic_input, dict):
        title = topic_input.get("title", "未知主题")
        content = topic_input.get("content", "")
    else:
        title = str(topic_input)
        content = ""

    logger.info(f"--- 启动: Smart Review 多智能体出题系统 (Title: {title}) ---")

    # 1. 获取客户端
    client = get_api_client()
    if not client:
        return None

    # 2. 获取模型配置 (强制使用 Chat 模型)
    # 直接使用配置里的普通模型，或者写死 "deepseek-chat"
    model_name = getattr(settings, "AGENT_QUIZ_MODEL", "deepseek-chat")

    # 3. 执行生成
    if callable(run_smart_quiz_pipeline):
        try:
            logger.info(f"🚀 正在调用 Smart Flow 流水线 (Model: {model_name})...")

            result = run_smart_quiz_pipeline(
                client=client,
                title=title,
                content=content,
                model_name=model_name
            )

            if result:
                logger.info(f"🎉 生成成功！\n{json.dumps(result, ensure_ascii=False, indent=2)}")
                return result
            else:
                logger.error("生成失败（流水线返回空）。")
                return None
        except Exception as e:
            logger.error(f"流水线内部发生错误: {e}", exc_info=True)
            return None
    else:
        logger.error("🛑 无法执行: 核心模块 'smart_flow' 未加载。")
        return None


if __name__ == "__main__":
    # 本地测试
    test_data = {
        "title": "纳维-斯托克斯方程",
        "content": "描述粘性不可压缩流体动量守恒的运动方程..."
    }
    run_quiz_generation(test_data)