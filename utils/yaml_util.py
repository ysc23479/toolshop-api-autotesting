# utils/yaml_util.py
import os
import yaml

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACT_PATH = os.path.join(BASE_DIR, "data", "extract.yaml")

def load_yaml(relative_path):
    """读取 YAML 文件，返回 Python 对象"""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(relative_path, data):
    """写入 YAML 文件"""
    full_path = os.path.join(BASE_DIR, relative_path)
    with open(full_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

def write_extract(data):
    """追加写入 extract.yaml，data 是 dict"""
    with open(EXTRACT_PATH, encoding="utf-8", mode="a+") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def read_extract(key, default=None):
    """从 extract.yaml 读取指定 key"""
    with open(EXTRACT_PATH, encoding="utf-8", mode="r") as f:
        all_value = yaml.safe_load(f) or {}
        return all_value.get(key, default)


def clear_extract():
    """清空 extract.yaml"""
    with open(EXTRACT_PATH, encoding="utf-8", mode="w") as f:
        f.truncate()