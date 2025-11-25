import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from openai import OpenAI

# --- 1. 导入配置与 Logger (完全保持你的项目风格) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    # 🌟 导入配置好的 logger 实例
    from src.utils.logger_config import logger
except ImportError as e:
    # Fallback for standalone testing if needed
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    print(f"WARNING: 无法导入 settings 或 logger，使用默认配置: {e}")
    # 创建一个 dummy settings 以防报错
    class Settings:
        DEEPSEEK_BASE_URL = "https://api.deepseek.com" # 默认地址
        AGENT_QUIZ_MODEL = "deepseek-chat" # 默认模型
    settings = Settings()

# --- 2. 核心鉴权逻辑 (复用你的代码) ---
def get_api_client():
    """初始化 API 客户端 (动态获取 Token，优先环境变量)"""
    try:
        # 🌟 优先从 os.environ 获取 (适配前端传入)
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

# --- 3. 定义数据结构 ---
@dataclass
class QuizItem:
    question: str
    options: List[str]
    answer: str
    analysis: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# --- 4. 智能体逻辑 ---
class QuizAgent:
    def __init__(self, client: OpenAI):
        self.client = client
        # 获取模型名称，如果 settings 里没有定义 AGENT_QUIZ_MODEL，则使用默认值
        self.model_name = getattr(settings, "AGENT_QUIZ_MODEL", "deepseek-chat")

    def _build_prompt(self, topic: str) -> str:
        return f"""
        任务：请根据知识点“{topic}”出一道单项选择练习题。
        
        要求：
        1. 题目难度适中，适合练手。
        2. 解析要极其简练（一两句话讲清楚原理）。
        3. 严格只返回 JSON 格式，不要包含 Markdown 标记（如 ```json）。
        
        JSON 格式模板：
        {{
            "question": "题干描述",
            "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
            "answer": "正确选项（完整文本，如 'B. 选项2'）",
            "analysis": "简短解析"
        }}
        """

    def generate(self, topic: str) -> Optional[Dict[str, Any]]:
        logger.info(f"[Agent] 正在为知识点 [{topic}] 生成题目...")
        
        prompt = self._build_prompt(topic)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "你是一个专业的出题助手，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3, # 稍微降低温度以保证格式稳定
                stream=False
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"[DEBUG] <<< API 响应片段: {content[:50]}...")

            # 清洗数据 (防止模型返回 Markdown 代码块)
            clean_json = content.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(clean_json)
            
            # 校验并构建对象
            quiz = QuizItem(
                question=data.get("question", "生成失败"),
                options=data.get("options", []),
                answer=data.get("answer", ""),
                analysis=data.get("analysis", "暂无解析")
            )
            
            return quiz.to_dict()

        except json.JSONDecodeError:
            logger.error(f"!!! JSON 解析失败。原始响应: {content}")
            return None
        except Exception as e:
            logger.error(f"!!! API 调用或处理失败: {e}", exc_info=True)
            return None

# --- 5. 运行入口 (类似于 run_classification) ---
def run_quiz_generation(topic_input: str):
    logger.info("--- 启动: 练习题生成智能体 (Quiz Agent) ---")
    
    # 1. 获取客户端 (自动处理 Token)
    client = get_api_client()
    if not client:
        logger.error("无法启动：客户端初始化失败。")
        return

    # 2. 初始化智能体
    agent = QuizAgent(client)

    # 3. 执行生成
    result = agent.generate(topic_input)

    # 4. 输出结果 (供前端或后续流程使用)
    if result:
        logger.info(f"生成成功！\n{json.dumps(result, ensure_ascii=False, indent=2)}")
        # 这里你可以选择将 result 保存到文件，或者直接 return 给调用的 API 接口
        return result
    else:
        logger.error("生成失败。")
        return None

if __name__ == "__main__":
    # 模拟前端传来的知识点
    test_topic = "纳维-斯托克斯方程"
    
    # 如果是在本地测试，可能需要手动设置一下临时的环境变量 (如果 settings 里没有)
    # os.environ["DEEPSEEK_API_KEY"] = "sk-xxxxxxxx" 

    run_quiz_generation(test_topic)