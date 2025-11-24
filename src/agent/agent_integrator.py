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
    # 🌟 导入配置好的 logger 实例
    from src.utils.logger_config import logger
except ImportError as e:
    # 如果在 logger 启动前就出错，我们只能用 print
    print(f"CRITICAL: 2_integrator.py 无法导入 settings 或 logger: {e}")
    sys.exit(1)

# --- 2. 核心整合逻辑 ---

# 🌟 【V2 升级】定义我们希望保留的元素类型
# 这将主动过滤掉 'Header', 'Footer', 'PageNumber', 'ImageCaption' 等噪音
# (这些类型名来自 'unstructured' 库的输出)
ALLOWED_ELEMENT_TYPES = {
    "Title",  # 标题
    "NarrativeText",  # 叙述性文本 (正文)
    "ListItem",  # 列表项
    "Text",  # 'unstructured' 的通用文本类别
    "Table",  # 表格 (通常被 'unstructured' 转换为文本)
    "Formula"  # 公式
}


def run_integration():
    """
    步骤2：整合者主函数。
    - 读取: settings.OUTPUT_PREPROCESSED (所有 .json 文件)
    - 写入: settings.OUTPUT_INTEGRATED / 'catalog_raw.json' (单一的目录文件)
    """

    # 🌟 使用 logger 代替 print
    logger.info("--- 步骤 2: 整合 (Integrating) ---")
    logger.info(f"将只保留以下元素类型: {ALLOWED_ELEMENT_TYPES}")

    input_dir = settings.OUTPUT_PREPROCESSED
    output_file = settings.OUTPUT_INTEGRATED / 'catalog_raw.json'  # 目标：单一的目录文件

    if not os.path.exists(input_dir):
        # 🌟
        logger.error(f"错误：找不到预处理目录 '{input_dir}'。请先运行步骤 1。")
        return

    # --- 收集所有预处理过的 .json 文件 (递归) ---
    json_files_to_process = []
    logger.info(f"正在扫描预处理目录: {input_dir}")
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                file_path = os.path.join(root, filename)
                # 计算相对路径 (例如: '数学/高数上/Chapter1.json')
                relative_path = os.path.relpath(file_path, input_dir)
                json_files_to_process.append((file_path, relative_path))

    if not json_files_to_process:
        logger.info("未找到预处理过的 .json 文件。")
        logger.info("完成: 整合。")
        return

    logger.info(f"扫描完成，找到 {len(json_files_to_process)} 个预处理文件准备整合。")

    # --- 开始整合 (Chunking) ---
    all_chunks = []  # 最终 'catalog_raw.json' 的内容

    for file_path, relative_path in tqdm(json_files_to_process, desc="整合进度"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                elements = json.load(f)

            if not elements:
                logger.warning(f"文件 {file_path} 为空，跳过。")
                continue

            # 按页码对元素进行分组
            pages = defaultdict(list)
            for el in elements:
                page_num = el.get('metadata', {}).get('page_number', 1)
                pages[page_num].append(el)

            # 移除 .json 后缀，得到 '数学/高数上/Chapter1'
            source_doc_id = os.path.splitext(relative_path)[0]

            for page_num, page_elements in sorted(pages.items()):  # 按页码排序

                # -----------------------------------------------------
                # 🌟 【V2 升级】开始：智能过滤 🌟
                # -----------------------------------------------------

                # 1. 过滤掉所有噪音元素
                filtered_elements = [
                    el for el in page_elements
                    if el.get('type') in ALLOWED_ELEMENT_TYPES
                ]

                # 2. 仅合并“干净”元素的文本
                content_list = [
                    el['text'] for el in filtered_elements
                    if el.get('text') and el.get('text').strip()
                ]

                # (旧代码已被替换)
                # -----------------------------------------------------
                # 🌟 【V2 升级】结束 🌟
                # -----------------------------------------------------

                content = "\n\n".join(content_list)  # 使用双换行符分隔元素

                # 如果页面在过滤后完全没有文本内容，则跳过
                if not content.strip():
                    logger.debug(f"跳过 {source_doc_id}_p{page_num} (过滤后为空)")
                    continue

                # 创建一个知识块 (Chunk)
                chunk = {
                    "chunk_id": f"{source_doc_id}_p{page_num}",  # 唯一的块ID
                    "source_document": source_doc_id,  # 来源文档
                    "page_number": page_num,  # 来源页码
                    "content": content,  # 整合后的【干净】文本内容
                }
                all_chunks.append(chunk)

        except json.JSONDecodeError:
            # 🌟 使用 logger 记录错误
            logger.error(f"!!! 文件 {file_path} JSON 解码失败，跳过。", exc_info=True)
        except Exception as e:
            # 🌟 使用 logger 记录错误
            logger.error(f"!!! 处理文件 {file_path} 时发生未知错误: {e}", exc_info=True)

    # --- 写入最终的"哑"目录文件 ---
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=4)

        logger.info(f"整合完成！共生成 {len(all_chunks)} 个【高信噪比】知识块(Chunks)。")
        logger.info(f"“哑”目录文件已保存到: {output_file}")

    except Exception as e:
        # 🌟
        logger.error(f"!!! 写入最终目录文件 {output_file} 时失败: {e}", exc_info=True)

    logger.info("完成: 整合。")


# --- 3. 独立运行 (用于测试) ---
if __name__ == "__main__":
    logger.info("--- (独立运行 2_integrator.py) ---")

    try:
        settings.setup_directories()
        logger.info("已调用 settings.setup_directories()。")
    except AttributeError:
        logger.warning("警告：'settings.setup_directories()' 函数未找到。")
        logger.warning("请确保 2_outputs 目录结构已手动创建。")
        os.makedirs(settings.OUTPUT_INTEGRATED, exist_ok=True)
    except NameError:
        logger.critical("错误: settings 导入失败，无法运行测试。")
        sys.exit(1)

    # 运行整合流程
    run_integration()