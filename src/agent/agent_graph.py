import json
import os
from configs import settings
from src.utils.logger_config import logger
from openai import OpenAI

# 尝试从设置中获取 Key，如果没有则留空（可能会报错，需确保 settings 里有 Key）
API_KEY = getattr(settings, 'OPENAI_API_KEY', os.getenv("OPENAI_API_KEY"))
BASE_URL = getattr(settings, 'OPENAI_BASE_URL', os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))

class AgentGraph:
    def __init__(self):
        # 你的最终输出目录
        self.kb_path = settings.OUTPUT_FINAL / 'Smart_Review_KB.json'
        self.graph_path = settings.OUTPUT_FINAL / 'graph_data.json'
        
        # 初始化 AI 客户端
        self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    def run_graph_generation(self):
        """主函数：生成知识图谱数据"""
        logger.info("--- [Step 5] 正在构建知识图谱 (Knowledge Graph) ---")

        if not self.kb_path.exists():
            logger.warning(f"找不到知识库文件: {self.kb_path}，跳过图谱生成。")
            return

        # 1. 读取已经生成的知识库
        with open(self.kb_path, 'r', encoding='utf-8') as f:
            kb_data = json.load(f)

        # 2. 构建节点 (Nodes)
        # 节点：图上的圆圈
        nodes = []
        titles = []
        for item in kb_data:
            title = item.get('title', '未命名')
            if title in titles: continue # 去重
            
            titles.append(title)
            # 内容越长，节点越大 (20~60之间)
            content_len = len(str(item.get('content', '')))
            symbol_size = min(max(content_len / 20, 20), 60)
            
            nodes.append({
                "id": title,
                "name": title,
                "symbolSize": symbol_size,
                "category": item.get('category', '核心知识'),
                "value": content_len, # 鼠标悬停显示的数值
                # 把详情藏在这里，前端点击时弹窗用
                "info": item.get('summary', item.get('content', '暂无详情'))
            })

        logger.info(f"提取到 {len(nodes)} 个知识节点，正在进行 AI 关联分析...")

        # 3. 构建连线 (Links)
        # 为了省钱且快，我们先用一种混合策略：
        # 策略A (关键词匹配): 如果 A 的内容里直接提到了 B，建立强连接
        # 策略B (AI分析): 让 AI 分析标题列表，补充逻辑连接
        
        links = []
        
        # --- 策略A: 关键词硬匹配 (免费、快速、准确) ---
        for i, n1 in enumerate(nodes):
            for n2 in nodes:
                if n1['name'] == n2['name']: continue
                # 如果 B 的名字出现在 A 的描述里
                if n2['name'] in n1['info']:
                    links.append({
                        "source": n1['name'],
                        "target": n2['name'],
                        "desc": "引用",
                        "lineStyle": {"curveness": 0.2}
                    })

        # --- 策略B: AI 补充深层逻辑 (可选) ---
        # 如果你想更智能，取消下面注释，让 AI 帮你找关系
        # (注意：这会消耗 token)
        try:
            ai_links = self._ask_ai_for_relations(titles)
            links.extend(ai_links)
        except Exception as e:
            logger.warning(f"AI 关联分析失败 (可能是网络或Key问题)，仅使用关键词匹配: {e}")

        # 4. 保存结果
        output_data = {
            "type": "force",
            "nodes": nodes,
            "links": links,
            "categories": [{"name": "核心知识"}, {"name": "基础概念"}]
        }

        with open(self.graph_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 图谱生成完毕! 数据已保存至: {self.graph_path}")

    def _ask_ai_for_relations(self, titles):
        """私有函数：调用 AI 分析关系"""
        # 为了防止 token 溢出，只取前 50 个重要标题
        short_list = titles[:50]
        prompt = f"请分析以下流体力学概念之间的关系，输出JSON格式的边列表：{json.dumps(short_list, ensure_ascii=False)}"
        
        # 这里需要读取 yaml 里的 system prompt，为简化直接写死或简写
        # 实际项目中建议用 settings.PROMPTS['agent_graph']
        
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo", # 或 settings.DEFAULT_MODEL
            messages=[
                {"role": "system", "content": "你是一个输出纯JSON的知识图谱助手。格式：[{\"source\":\"A\",\"target\":\"B\",\"desc\":\"关系\"}]"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        content = response.choices[0].message.content
        # 清洗一下 markdown 标记
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)