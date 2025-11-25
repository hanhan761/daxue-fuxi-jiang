# src/feiman/quiz_agent.py

import os
import sys
import json
from openai import OpenAI

# 导入配置
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
    # Dummy settings if needed...

# 导入新的流水线
from src.feiman.smart_flow.pipeline import run_smart_quiz_pipeline


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