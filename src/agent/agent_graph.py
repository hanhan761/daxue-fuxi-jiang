import os
import sys
import json
import yaml
from openai import OpenAI
from pathlib import Path

# --- 1. 环境设置 ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError:
    sys.exit(1)

# --- 2. 辅助函数 ---
def get_api_client():
    key = os.environ.get("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", "")
    if not key: return None
    return OpenAI(api_key=key, base_url=settings.DEEPSEEK_BASE_URL)

def load_prompts():
    try:
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except: return None

# --- 3. 核心逻辑 ---
def run_graph_building():
    logger.info("=================================================")
    logger.info("===   🕸️ 步骤 5.5: 构建图谱 (Graphing) 启动   ===")
    logger.info("=================================================")

    input_dir = settings.OUTPUT_UNIFIED
    output_dir = settings.OUTPUT_GRAPH_EDGES
    output_file = output_dir / "relationships.json"

    if not input_dir.exists():
        logger.error(f"❌ 输入目录不存在: {input_dir}")
        return

    # 1. 收集所有知识点标题
    titles = []
    files = list(input_dir.glob("*.json"))
    if not files:
        logger.warning("⚠️ 没有知识点文件，跳过构图。")
        return

    logger.info(f"🔍 正在扫描 {len(files)} 个知识点...")
    for f in files:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if data.get("title"):
                titles.append(data.get("title"))
        except: pass

    if len(titles) < 2:
        logger.info("⚠️ 知识点太少，无法构建图谱。")
        return

    # 2. 调用 AI 分析关联
    client = get_api_client()
    prompts = load_prompts()
    if not client or not prompts: return

    logger.info("🤖 正在请求 AI 分析知识点关联 (这可能需要几十秒)...")
    
    # 限制列表长度，防止 Token 溢出 (假设最多处理前 100 个核心概念)
    safe_titles = titles[:100] 
    titles_str = json.dumps(safe_titles, ensure_ascii=False)

    try:
        # 使用 agent_prompts.yaml 里定义的 agent_graph 提示词
        prompt_config = prompts.get('agent_graph', {})
        system_prompt = prompt_config.get('role', 'system') # 这里 yaml 结构有点不一样，适配一下
        if isinstance(prompt_config, dict) and 'instruction' in prompt_config:
             # 适配你 yaml 的格式
            sys_msg = prompt_config['instruction']
            user_msg = f"请分析以下知识点列表：\n{titles_str}"
        else:
            # 兜底 Prompt
            sys_msg = "你是一个知识图谱专家。请分析给定的标题列表，返回它们之间最强的逻辑关联。格式必须是 JSON 列表：[{'source':'A','target':'B','desc':'关系'}]。只输出 JSON。"
            user_msg = titles_str

        response = client.chat.completions.create(
            model=settings.AGENT_UNIFIER_MODEL, # 借用 Unifier 的高智商模型
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.1,
            stream=False
        )
        
        result = response.choices[0].message.content.strip()
        # 清洗 Markdown
        if result.startswith("```json"): result = result[7:]
        if result.endswith("```"): result = result[:-3]
        
        edges = json.loads(result.strip())
        
        # 3. 保存结果
        output_dir.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(edges, f, ensure_ascii=False, indent=4)
            
        logger.info(f"✅ 图谱构建完成！生成了 {len(edges)} 条关联。")
        
    except Exception as e:
        logger.error(f"❌ 构建图谱失败: {e}")

if __name__ == "__main__":
    settings.setup_directories()
    run_graph_building()