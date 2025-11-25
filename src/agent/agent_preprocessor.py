import os
import sys
import json
from tqdm import tqdm
import nltk
# 引入原生处理库
try:
    from pptx import Presentation
    import pdfplumber
    from docx import Document
except ImportError:
    print("请先安装依赖: pip install python-pptx pdfplumber python-docx")
    sys.exit(1)

from collections import Counter
# 保留 unstructured 作为兜底方案 (处理 html, jpg 等其他格式)
from unstructured.partition.auto import partition
from unstructured.cleaners.core import clean, clean_extra_whitespace

# --- 1. 导入配置与 Logger ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError as e:
    print(f"CRITICAL: 1_preprocessor.py 无法导入 settings 或 logger: {e}")
    sys.exit(1)


# --- 2. 专用提取函数群 ---

def process_txt_native(file_path):
    """处理 TXT: 直接读取"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return [{
            "id": "txt_full",
            "type": "Text",
            "text": content,
            "metadata": {"filename": os.path.basename(file_path)}
        }]
    except Exception as e:
        logger.error(f"TXT 读取失败: {e}")
        return []

def process_pptx_native(file_path):
    """处理 PPTX: 递归遍历所有 Shape，按 Slide 聚合"""
    elements = []
    try:
        prs = Presentation(file_path)
        
        # 递归提取函数：处理 Group 组合图形
        def extract_shape_text(shape):
            text_parts = []
            # 1. 提取文本框内容
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        text_parts.append(text)
            # 2. 提取表格内容
            if shape.has_table:
                for row in shape.table.rows:
                    row_text = " | ".join([cell.text_frame.text.strip() for cell in row.cells if cell.text_frame.text.strip()])
                    if row_text:
                        text_parts.append(row_text)
            # 3. 递归处理组合图形 (Group)
            if shape.shape_type == 6: # MSO_SHAPE_TYPE.GROUP
                for child in shape.shapes:
                    text_parts.extend(extract_shape_text(child))
            return text_parts

        for i, slide in enumerate(prs.slides):
            page_num = i + 1
            page_content = []
            
            # 遍历所有形状 (不仅仅是 placeholders)
            for shape in slide.shapes:
                texts = extract_shape_text(shape)
                if texts:
                    page_content.extend(texts)
            
            # 如果这一页有字，聚合为一个 Text 块
            if page_content:
                full_text = "\n".join(page_content)
                elements.append({
                    "id": f"pptx_p{page_num}",
                    "type": "Text", # 统一为 Text，交给 LLM 去区分标题和正文
                    "text": full_text,
                    "metadata": {"page_number": page_num, "filename": os.path.basename(file_path)}
                })
    except Exception as e:
        logger.error(f"PPTX 解析失败 [{os.path.basename(file_path)}]: {e}")
    return elements

def process_pdf_native(file_path):
    """处理 PDF: 使用 pdfplumber 按页物理提取"""
    elements = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                # extract_text(layout=True) 尝试保留物理布局
                text = page.extract_text(layout=False) 
                if text and text.strip():
                    elements.append({
                        "id": f"pdf_p{i+1}",
                        "type": "Text",
                        "text": text.strip(),
                        "metadata": {"page_number": i+1, "filename": os.path.basename(file_path)}
                    })
    except Exception as e:
        logger.error(f"PDF 解析失败 [{os.path.basename(file_path)}]: {e}")
    return elements

def process_docx_native(file_path):
    """处理 DOCX: 遍历段落和表格"""
    elements = []
    try:
        doc = Document(file_path)
        full_text = []
        
        # 简单粗暴策略：按顺序读取所有段落和表格，拼接成一个大文本流
        # (也可以选择按“页”大概切分，但Word没有严格的页概念，通常按整个文档或章节处理)
        
        # 这里演示：将整个文档作为一个大的 Text 块 (或者你可以按每 10 个段落切分)
        # 为了给 LLM 好的上下文，我们尽量保留连续性
        
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())
        
        # 简单的表格提取 (追加在段落后，或者你可以尝试穿插，但 python-docx 穿插读取比较麻烦)
        # 实际上 Word 的段落和表格是按顺序存储在 doc.element.body 中的，如果追求极致顺序，需要解析 XML
        # 这里采用简单策略：先段落后表格 (适合只有文末附件表格的情况)，
        # 或者使用 unstructured 处理 docx 其实效果还行。
        # 但既然要 native，我们可以只提段落，或者做简单处理。
        
        # *改进版*：按 XML 顺序遍历 (伪代码逻辑，简化实现)
        # 鉴于 python-docx 混合读取比较复杂，我们这里先只读取段落。
        # 如果 DOCX 表格非常重要，建议 DOCX 依然保留使用 unstructured，或者使用专门的 docx2txt 库。
        
        # 让我们尝试一种折中：只把表格作为补充文本附在最后，或者仅提取段落。
        # 大部分课件 Word 都是大段文字。
        
        # 使用 Unstructured 处理 DOCX 其实往往比手写 XML 解析要好，
        # 所以对于 DOCX，我们可以选择 **兜底使用 Unstructured**，除非你有非常特殊的表格需求。
        # 这里我演示如何用 Native 读段落：
        
        pass # 实际逻辑在下方 router 中决定是否使用 native
        
    except Exception as e:
        logger.error(f"DOCX 解析失败: {e}")
    return elements

# --- 3. 主路由逻辑 ---

def run_preprocessing():
    """
    预处理主入口：根据文件扩展名分发给不同的提取器
    """
    logger.info("--- 步骤 1: 预处理 (Pre-processing) [Native Mode] ---")
    
    input_dir = settings.INPUTS_DIR
    output_dir = settings.OUTPUT_PREPROCESSED
    
    if not input_dir.exists():
        logger.error(f"输入目录不存在: {input_dir}")
        return

    files_to_process = []
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.startswith('.'): continue
            files_to_process.append(os.path.join(root, filename))

    logger.info(f"扫描完成，找到 {len(files_to_process)} 个文件。")
    
    success_count = 0
    for file_path in tqdm(files_to_process, desc="处理进度"):
        file_ext = os.path.splitext(file_path)[1].lower()
        output_data = []
        
        # --- 路由分发 ---
        if file_ext == '.txt':
            output_data = process_txt_native(file_path)
            
        elif file_ext == '.pptx':
            output_data = process_pptx_native(file_path)
            
        elif file_ext == '.pdf':
            output_data = process_pdf_native(file_path)
            
        elif file_ext == '.docx':
            # 对于 DOCX，如果你发现 Native 提取表格太麻烦，
            # 可以直接回退到 unstructured，它对 docx 支持通常不错。
            # 或者使用 python-docx 提取纯文本。
            # 这里为了稳妥，DOCX 我们演示继续使用 unstructured，
            # 除非你想只提取纯文本段落。
            try:
                # logger.info(f"使用 Unstructured 处理 DOCX: {os.path.basename(file_path)}")
                elements = partition(filename=file_path)
                for el in elements:
                    if hasattr(el, 'text') and el.text.strip():
                        output_data.append({
                            "id": str(el.id),
                            "type": "Text",
                            "text": el.text.strip(),
                            "metadata": {"filename": os.path.basename(file_path)}
                        })
            except Exception as e:
                logger.error(f"DOCX (Unstructured) 解析失败: {e}")

        else:
            # 其他格式 (jpg, html, etc.) -> 兜底
            try:
                elements = partition(filename=file_path)
                for el in elements:
                    if hasattr(el, 'text') and el.text.strip():
                        output_data.append({
                            "id": str(el.id),
                            "type": "Text",
                            "text": el.text.strip(),
                            "metadata": {"filename": os.path.basename(file_path)}
                        })
            except Exception as e:
                logger.error(f"兜底解析失败 [{file_ext}]: {e}")

        # --- 保存结果 ---
        if output_data:
            relative_path = os.path.relpath(file_path, input_dir)
            output_json_path = output_dir / (os.path.splitext(relative_path)[0] + '.json')
            output_json_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            success_count += 1
        else:
            logger.warning(f"跳过空文件或解析失败: {os.path.basename(file_path)}")

    logger.info(f"预处理完成。成功: {success_count}/{len(files_to_process)}")

if __name__ == "__main__":
    settings.setup_directories()
    run_preprocessing()