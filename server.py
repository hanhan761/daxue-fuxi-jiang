import sys
import os
import webbrowser
import importlib
import shutil
import uuid
from threading import Timer
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path

# 确保项目根目录在Python路径中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from configs import settings
from src.utils.logger_config import logger
import src

settings.setup_directories()
logger.info(">>> 系统初始化... 目录结构已创建")

try:
    import src.orchestrator 

    app = Flask(__name__)
    CORS(app)

    BASE_TEMP_DIR = getattr(settings, 'TEMP_DIR', Path(PROJECT_ROOT) / 'temp_uploads')

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return {"status": "ok"}

    @app.route('/api/generate_kb', methods=['POST'])
    def generate_kb():
        # 生成唯一任务ID，隔离不同请求的文件
        request_id = str(uuid.uuid4())
        current_task_dir = BASE_TEMP_DIR / request_id
        
        try:
            logger.info(f">>> [任务 {request_id}] 收到生成请求")
            
            kb_name = request.form.get('kb_name', 'AI_Generated_KB')
            api_token = request.form.get('api_token')
            uploaded_files = request.files.getlist('files')

            if not api_token:
                return jsonify({'error': '未提供 Token'}), 400
            
            os.environ['DEEPSEEK_API_KEY'] = api_token
            importlib.reload(src.orchestrator)
            
            # 1. 保存上传文件 (Input)
            if not current_task_dir.exists():
                current_task_dir.mkdir(parents=True, exist_ok=True)

            for file in uploaded_files:
                filename = secure_filename(file.filename)
                file.save(str(current_task_dir / filename))
            
            # 2. 运行流水线
            # orchestrator 内部会处理中间文件的产生和清理
            generated_file_path = src.orchestrator.run_pipeline(input_dir=str(current_task_dir))
            
            if not generated_file_path:
                raise Exception("Pipeline 执行失败，请检查后端日志")

            # 3. 读取并返回结果
            if os.path.exists(generated_file_path):
                import json
                with open(generated_file_path, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                
                # 确保名字正确
                if 'graph_metadata' in result_data:
                    result_data['graph_metadata']['name'] = kb_name
                
                node_count = len(result_data.get('nodes', []))
                logger.info(f"任务完成，返回 {node_count} 个节点")
                
                return jsonify(result_data)
            else:
                raise Exception("生成的最终文件丢失")

        except Exception as e:
            logger.exception(f"任务 [{request_id}] 失败")
            return jsonify({'error': str(e)}), 500
            
        finally:
            # 4. [关键] 清理输入文件
            # 无论成功失败，用户上传的 PDF/PPT 都应该被删除
            if current_task_dir.exists():
                try:
                    shutil.rmtree(current_task_dir)
                    logger.info(f"任务 [{request_id}] 输入临时文件已清理")
                except Exception as cleanup_error:
                    logger.error(f"清理输入目录失败: {cleanup_error}")

    def open_browser():
        try:
            webbrowser.open('file://' + os.path.abspath("start.html"))
        except:
            pass

    if __name__ == '__main__':
        print("🚀 服务器启动中...")
        Timer(1.5, open_browser).start()
        app.run(debug=False, port=5000)

except Exception as e:
    print(f"启动失败: {e}")