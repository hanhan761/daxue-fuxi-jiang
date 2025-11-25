import os
import ast

# --- ⚙️ 配置项 ---
# 扫描时忽略的文件夹（避免扫描虚拟环境或git目录）
IGNORE_DIRS = {
    '.git', '__pycache__', '.idea', '.vscode', 'venv', 'env', 
    'build', 'dist', 'egg-info', 'node_modules'
}

def parse_py_file(file_path):
    """
    解析 Python 文件，返回结构化的定义列表。
    返回格式: [{'type': 'class', 'name': 'X', 'methods': [...]}, {'type': 'func', 'name': 'Y'}]
    """
    items = []
    try:
        with open(file_path, "r", encoding="utf-8", errors='ignore') as f:
            source = f.read()
            if not source.strip():
                return []
            tree = ast.parse(source)

        for node in tree.body:
            # 1. 提取类及其方法
            if isinstance(node, ast.ClassDef):
                methods = []
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(sub.name)
                items.append({
                    'type': 'class',
                    'name': node.name,
                    'methods': methods
                })
            
            # 2. 提取顶级函数
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                items.append({
                    'type': 'func',
                    'name': node.name
                })
                
    except Exception as e:
        return [{'type': 'error', 'msg': str(e)}]
    
    return items

def print_tree(startpath):
    print("="*60)
    print(f"📂 项目结构全扫描: {os.path.abspath(startpath)}")
    print("="*60)

    file_count = 0
    
    for root, dirs, files in os.walk(startpath):
        # 修改 dirs 列表以跳过忽略的目录 (原地修改生效)
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        # 计算当前层级，用于缩进
        level = root.replace(startpath, '').count(os.sep)
        indent = '    ' * level
        sub_indent = '    ' * (level + 1)
        
        # 打印当前文件夹名 (除了根目录)
        folder_name = os.path.basename(root)
        if folder_name:
            print(f"{indent}📁 {folder_name}/")
        
        # 遍历文件
        for f in sorted(files):
            if f.endswith('.py'):
                file_count += 1
                full_path = os.path.join(root, f)
                print(f"{sub_indent}🐍 {f}")
                
                # 解析内容
                definitions = parse_py_file(full_path)
                
                # 打印定义
                if not definitions:
                    print(f"{sub_indent}    (空文件或无定义)")
                
                for item in definitions:
                    details_indent = sub_indent + "    "
                    
                    if item['type'] == 'error':
                        print(f"{details_indent}❌ 解析失败: {item['msg']}")
                    
                    elif item['type'] == 'class':
                        print(f"{details_indent}🔵 class {item['name']}")
                        # 打印类里面的方法
                        for method in item['methods']:
                            # 忽略 __init__ 等魔术方法，让输出更清爽？(根据需要决定，这里选择保留)
                            print(f"{details_indent}    └── def {method}")
                            
                    elif item['type'] == 'func':
                        print(f"{details_indent}🟠 def {item['name']}")

    print("\n" + "-"*60)
    print(f"✅ 扫描完成，共发现 {file_count} 个 Python 文件。")

if __name__ == "__main__":
    # 扫描当前脚本所在目录
    print_tree(os.getcwd())