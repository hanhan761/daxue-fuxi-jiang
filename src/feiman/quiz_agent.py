import os
import sys
import json
from openai import OpenAI
import logging

# --- 1. 环境路径配置 ---
# 确保能找到项目根目录 (即 src 的上一级)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# --- 2. 容错导入配置与 Logger ---
try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError as e:
    # 如果导入失败，配置一个临时的 logger 和 settings，防止程序直接崩溃
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ [Init Warning] 无法导入 settings 或 logger: {e}")


    # [关键修复] 定义保底配置类，防止后面调用 settings.XXX 时报错
    class Settings:
        DEEPSEEK_BASE_URL = "https://api.deepseek.com"
        AGENT_QUIZ_MODEL = "deepseek-chat"
        SMART_MODEL_NAME = "deepseek-chat"  # 确保新功能用到的字段也有默认值
        DEEPSEEK_API_KEY = None


    settings = Settings()

# --- 3. 导入业务逻辑 (Smart Flow) ---
try:
    # 尝试导入多智能体流水线
    # ⚠️ 请确保 src/feiman/smart_flow/ 目录下有 __init__.py 文件！
    from src.feiman.smart_flow.pipeline import run_smart_quiz_pipeline
except ImportError as e:
    logger.error(f"❌ 严重错误: 无法导入 smart_flow 模块。请检查 src/feiman/smart_flow/__init__.py 是否存在。详情: {e}")
    # 设置为 None，稍后在调用时进行安全检查
    run_smart_quiz_pipeline = None


# --- 4. 核心鉴权逻辑 (保持原样) ---
def get_api_client():
    """初始化 API 客户端 (动态获取 Token，优先环境变量)"""
    try:
        # 优先从 os.environ 获取 (适配前端传入)
        current_api_key = os.environ.get("DEEPSEEK_API_KEY")
        source = "环境变量 (os.environ)"

        if not current_api_key:
            current_api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
            source = "配置文件 (settings)"

        if not current_api_key:
            logger.error("CRITICAL: 未检测到 API Key。请在前端输入 Token。")
            return None

        # [DEBUG] 打印 API Key 信息 (脱敏)
        masked_key = current_api_key[:8] + "***" + current_api_key[-4:] if len(current_api_key) > 12 else "***"
        logger.info(f"[DEBUG] API 客户端初始化中... 来源: {source}, Key: {masked_key}")

        client = OpenAI(
            api_key=current_api_key,
            base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        return client
    except Exception as e:
        logger.error(f"Error: 初始化客户端失败: {e}", exc_info=True)
        return None


# --- 5. 运行入口 (对接 Smart Flow v2) ---
def run_quiz_generation(topic_input):
    """
    执行智能出题流程。

    Args:
        topic_input: 可以是字符串 (旧版兼容，只含标题)
                     或者是字典 {'title': '...', 'content': '...'} (新版，包含详细背景)
    """

    # [核心逻辑] 解析输入数据
    title = ""
    content = ""

    if isinstance(topic_input, dict):
        # 如果是字典，提取 title 和 content
        title = topic_input.get("title", "未知主题")
        content = topic_input.get("content", "")  # 允许 content 为空
    else:
        # 如果是字符串，说明是旧接口调用，仅作为标题
        title = str(topic_input)
        content = ""

    logger.info(f"--- 启动: Smart Review 多智能体出题系统 (Title: {title}) ---")
    if content:
        logger.info(f"    (包含背景内容，长度: {len(content)} 字符)")

    # 1. 获取客户端
    client = get_api_client()
    if not client:
        logger.error("无法启动：客户端初始化失败。")
        return None

    # 2. 获取模型配置
    # 优先用 SMART_MODEL_NAME (如 deepseek-reasoner)，如果没有则用默认的 AGENT_QUIZ_MODEL
    model_name = getattr(settings, "SMART_MODEL_NAME", None)
    if not model_name:
        model_name = getattr(settings, "AGENT_QUIZ_MODEL", "deepseek-chat")

    # 3. 执行生成 (带安全检查)
    if callable(run_smart_quiz_pipeline):
        try:
            logger.info(f"🚀 正在调用 Smart Flow 流水线 (Model: {model_name})...")

            # [核心逻辑] 调用新版 Pipeline，传入 title 和 content
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
        # 如果导入失败了，这里会优雅地输出错误
        logger.error(
            "🛑 无法执行: 核心模块 'smart_flow' 未加载。请确认 src/feiman/smart_flow/__init__.py 存在且代码无误。")
        return None


if __name__ == "__main__":
    # 本地测试代码 (模拟新版数据结构)
    test_data = {
        "title": "纳维-斯托克斯方程",
        "content": "纳维-斯托克斯方程（Navier-Stokes equations），是描述粘性不可压缩流体动量守恒的运动方程..."
    }

    # 如果本地测试没有环境变量，可以在此临时设置
    # os.environ["DEEPSEEK_API_KEY"] = "sk-xxxxxxxx"

    run_quiz_generation(test_data)