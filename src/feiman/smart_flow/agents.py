# src/feiman/smart_flow/agents.py
import logging

logger = logging.getLogger(__name__)


class SmartAgent:
    def __init__(self, name: str, role_prompt: str, client, model_name: str = None):
        self.name = name
        self.role_prompt = role_prompt
        self.client = client
        self.model_name = model_name or "deepseek-chat"  # 默认模型

    def work(self, task_input: str) -> str:
        logger.info(f"🤖 [{self.name}] 正在思考...")

        messages = [
            {"role": "system", "content": self.role_prompt},
            {"role": "user", "content": task_input}
        ]

        # 针对推理模型（如 deepseek-reasoner/R1）的特殊处理
        # 如果模型不支持 system role，将其拼接到 user
        if "reasoner" in self.model_name:
            messages = [
                {"role": "user", "content": f"【你的角色设定】\n{self.role_prompt}\n\n【任务】\n{task_input}"}
            ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,  # 保持一定的创造性
                stream=False
            )
            result = response.choices[0].message.content.strip()
            # logger.debug(f"✅ [{self.name}] 输出: {result[:50]}...") # 调试用
            return result
        except Exception as e:
            logger.error(f"❌ [{self.name}] 发生错误: {e}")
            return "Error generating response"