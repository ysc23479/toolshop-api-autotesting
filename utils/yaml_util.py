import os
import yaml

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# YAML 反序列化
def load_yaml(relative_path):
    """读取 YAML 文件，返回 Python 对象(字典或列表)"""
    full_path = os.path.join(BASE_DIR, relative_path) #将根目录与相对路径拼接成完整绝对路径
    with open(full_path, encoding="utf-8") as f:
        return yaml.safe_load(f)

# YAML序列化
def write_yaml(relative_path, data):
    """将 Python 对象写入 YAML 文件"""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)