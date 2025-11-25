import logging

logger = logging.getLogger(__name__)


class SmartAgent:
    def __init__(self, name: str, role_prompt: str, client, model_name: str = None):
        self.name = name
        self.role_prompt = role_prompt
        self.client = client
        self.model_name = model_name or "deepseek-chat"

    def work(self, task_input: str) -> str:
        # logger.info(f"🤖 [{self.name}] 正在思考...") # 如果觉得日志太吵可以注释掉

        # 标准 Chat 模式构建消息
        messages = [
            {"role": "system", "content": self.role_prompt},
            {"role": "user", "content": task_input}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,  # Chat 模型保持适度创造性
                stream=False
            )
            result = response.choices[0].message.content.strip()
            return result
        except Exception as e:
            logger.error(f"❌ [{self.name}] 发生错误: {e}")
            return "Error generating response"