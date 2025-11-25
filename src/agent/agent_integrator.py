import os
import sys
import json
from tqdm import tqdm
from collections import defaultdict

# --- 1. 导入配置与 Logger ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError as e:
    print(f"CRITICAL: 2_integrator.py 无法导入 settings 或 logger: {e}")
    sys.exit(1)

# --- 2. 核心整合逻辑 ---

# 🌟 配置窗口策略
# WINDOW_SIZE: 每个 Chunk 包含多少页的内容 (建议 3-5 页，取决于 PPT 密度)
# OVERLAP: 是否重叠 (建议 True，保证跨页知识点不被切断)
WINDOW_SIZE = 3 

def run_integration():
    """
    步骤2：整合者主函数 (V3: 滑动窗口版)。
    - 读取: settings.OUTPUT_PREPROCESSED
    - 逻辑: 将连续的页码合并为一个大的 Context Chunk
    - 写入: settings.OUTPUT_INTEGRATED / 'catalog_raw.json'
    """
    logger.info("--- 步骤 2: 整合 (Integrating) [V3: Sliding Window] ---")
    logger.info(f"配置: 窗口大小={WINDOW_SIZE}页 (用于构建上下文)")

    input_dir = settings.OUTPUT_PREPROCESSED
    output_file = settings.OUTPUT_INTEGRATED / 'catalog_raw.json'

    if not input_dir.exists():
        logger.error(f"错误：找不到预处理目录 '{input_dir}'。")
        return

    # 1. 扫描文件
    json_files = []
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            if f.endswith('.json'):
                json_files.append(os.path.join(root, f))
    
    if not json_files:
        logger.warning("未找到预处理文件。")
        return

    all_chunks = []

    for file_path in tqdm(json_files, desc="整合进度"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                elements = json.load(f)
            
            if not elements: continue

            # 2. 按页码聚合内容
            # 先把每一页的内容拼成一个字符串
            pages_map = defaultdict(list)
            file_meta = elements[0].get('metadata', {})
            filename = file_meta.get('filename', os.path.basename(file_path))
            source_id = os.path.splitext(filename)[0]

            for el in elements:
                # 🌟 【改动1】移除类型过滤，只要有 text 就收
                text = el.get('text', '').strip()
                if not text: continue
                
                # 获取页码，如果没有则默认为 1 (比如 txt/docx)
                p_num = el.get('metadata', {}).get('page_number', 1)
                pages_map[p_num].append(text)

            # 将页码排序
            sorted_page_nums = sorted(pages_map.keys())
            
            # 如果是无页码文档(如txt)，或者只有1页，直接作为一个块
            if len(sorted_page_nums) <= 1:
                full_text = "\n\n".join(["\n".join(texts) for texts in pages_map.values()])
                all_chunks.append({
                    "chunk_id": f"{source_id}_full",
                    "source_document": filename,
                    "page_number": "All",
                    "content": full_text
                })
                continue

            # 3. 【改动2】执行滑动窗口 (Sliding Window)
            # 遍历页码列表，生成窗口
            # 这里的 i 是索引，不是页码
            for i in range(len(sorted_page_nums)):
                # 取出当前窗口内的页码索引: i 到 i + WINDOW_SIZE
                window_indices = sorted_page_nums[i : i + WINDOW_SIZE]
                
                # 如果是最后几页，且不足窗口大小，且不是起始页，可以选择跳过(避免重复)
                # 但为了保证覆盖，我们允许最后一个窗口较小
                
                window_content = []
                page_labels = []
                
                for p_num in window_indices:
                    # 每一页的内容
                    page_text = "\n".join(pages_map[p_num])
                    # 添加页码标记，方便 LLM 区分
                    window_content.append(f"--- [Page {p_num}] ---\n{page_text}")
                    page_labels.append(str(p_num))
                
                combined_text = "\n\n".join(window_content)
                
                # 构造 Chunk
                # ID 格式: doc_p1-p3
                start_p = page_labels[0]
                end_p = page_labels[-1]
                chunk_range = f"p{start_p}" if start_p == end_p else f"p{start_p}-{end_p}"
                
                all_chunks.append({
                    "chunk_id": f"{source_id}_{chunk_range}",
                    "source_document": filename,
                    "page_number": chunk_range, # 显示范围
                    "content": combined_text
                })

                # 🌟 优化策略：
                # 如果你想减少 Token 消耗，可以设置 step=WINDOW_SIZE (无重叠)
                # 如果你想增加连贯性，保持 step=1 (当前循环就是 step=1)
                # 这里默认 step=1，每个 Chunk 都是一个新的切入点

        except Exception as e:
            logger.error(f"处理文件 {os.path.basename(file_path)} 失败: {e}")

    # 4. 写入结果
    try:
        settings.OUTPUT_INTEGRATED.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=4)
        logger.info(f"整合完成！生成 {len(all_chunks)} 个上下文块。")
    except Exception as e:
        logger.error(f"写入失败: {e}")

if __name__ == "__main__":
    settings.setup_directories()
    run_integration()