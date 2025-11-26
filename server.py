import sys
import os
import webbrowser
import importlib
import shutil
import uuid
import json
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

# --- 1. 导入业务模块 ---
# 导入 orchestrator (生成知识库流水线)
try:
    import src.orchestrator
except ImportError as e:
    logger.error(f"无法导入 src.orchestrator: {e}")

# 导入 quiz_agent (费曼技巧出题智能体)
try:
    import src.feiman.quiz_agent
except ImportError as e:
    logger.error(f"无法导入 src.feiman.quiz_agent: {e}")


# 初始化目录
settings.setup_directories()
logger.info(">>> 系统初始化... 目录结构已创建")

try:
    app = Flask(__name__)
    CORS(app) # 允许跨域，方便前端开发调试

    BASE_TEMP_DIR = getattr(settings, 'TEMP_DIR', Path(PROJECT_ROOT) / 'temp_uploads')

    # --- 路由: 健康检查 ---
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return {"status": "ok"}

    # --- 路由: 费曼技巧 - AI 出题 (新增) ---
    @app.route('/api/feynman', methods=['POST'])
    def feynman_quiz():
        """
        接收知识点 topic 和 api_token，调用 quiz_agent 生成题目
        """
        try:
            # 获取 JSON 数据
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body must be JSON'}), 400

            topic = data.get('topic')
            api_token = data.get('api_token')

            if not topic:
                return jsonify({'error': '缺少 topic 参数'}), 400
            if not api_token:
                return jsonify({'error': '缺少 api_token 参数'}), 400

            # 1. 设置环境变量 (供 Agent 内部使用)
            os.environ['DEEPSEEK_API_KEY'] = api_token
            
            # 2. 重新加载模块 (确保 Token 更新生效，无需重启服务)
            importlib.reload(src.feiman.quiz_agent)

            logger.info(f">>> [费曼模式] 收到请求: Topic='{topic}'")

            # 3. 调用智能体生成题目
            # run_quiz_generation 返回的是一个字典 (QuizItem.to_dict())
            result = src.feiman.quiz_agent.run_quiz_generation(topic)

            if result:
                logger.info(f"[费曼模式] 生成成功: {result.get('question')[:20]}...")
                return jsonify(result)
            else:
                logger.error("[费曼模式] 生成失败，Agent 返回 None")
                return jsonify({'error': 'AI 生成题目失败，请检查日志或 Token 是否有效'}), 500

        except Exception as e:
            logger.exception(f"[费曼模式] 接口发生异常: {e}")
            return jsonify({'error': str(e)}), 500


    # --- 路由: 生成知识库 (原有功能) ---
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
            
            # 设置环境变量并重载模块
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

# =================================================================
# [新增接口] 知识图谱数据专用通道
# =================================================================
    @app.route('/api/graph', methods=['GET'])
    def get_knowledge_graph():
        """
        前端 ECharts 通过这个接口获取 graph_data.json
        """
        try:
            # settings.OUTPUT_FINAL 是存放最终结果的文件夹 (2_outputs/5_final)
            # 我们让 Flask 直接把里面的 graph_data.json 发给前端
            directory = settings.OUTPUT_FINAL
            filename = 'graph_data.json'
            
            # 检查文件是否存在
            file_path = directory / filename
            if not file_path.exists():
                return jsonify({"error": "图谱数据尚未生成，请先点击'开始处理'并等待完成"}), 404
                
            return send_from_directory(directory, filename)
            
        except Exception as e:
            logger.error(f"获取图谱数据失败: {e}")
            return jsonify({"error": str(e)}), 500


    # --- 辅助: 自动打开浏览器 ---
    def open_browser():
        try:
            # 确保这里指向你正确的前端入口文件
            webbrowser.open('file://' + os.path.abspath("start.html"))
        except:
            pass

    # --- 启动服务器 ---
    if __name__ == '__main__':
        print("🚀 服务器启动中...")
        print(f"📡 监听端口: 5000")
        print(f"📂 根目录: {PROJECT_ROOT}")
        
        # 稍微延迟一点打开浏览器，等待 Flask 启动
        Timer(1.5, open_browser).start()
        
        # 生产环境建议 debug=False
        app.run(debug=False, port=5000)

except Exception as e:
    print(f"CRITICAL: 服务器启动失败: {e}")