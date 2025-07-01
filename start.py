#!/usr/bin/env python3
"""
InfluFlow Backend 本地启动脚本
支持本地开发时启动API或UI服务
云平台部署使用Dockerfile中的supervisor配置
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import argparse

def setup_environment():
    """设置环境"""
    # 优先从.env文件加载环境变量，方便本地开发
    load_dotenv()
    
    # 确保在正确的目录
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

def validate_api_keys():
    """验证必需的API密钥"""
    # 对于influflow，只需要OPENAI_API_KEY
    required_keys = ['OPENAI_API_KEY']
    missing_keys = []
    
    for key in required_keys:
        if not os.environ.get(key):
            missing_keys.append(key)
    
    if missing_keys:
        print(f"❌ 缺少必需的环境变量: {', '.join(missing_keys)}")
        print("请在云平台dashboard中设置这些环境变量")
        return False
    
    print("✅ API密钥验证通过")
    return True



def start_api():
    """启动FastAPI服务器"""
    print("🚀 启动InfluFlow AI Backend API...")
    
    # 验证环境
    if not validate_api_keys():
        sys.exit(1)
    
    # 设置端口
    port = os.environ.get('PORT', '8000')
    
    # 使用uv run启动uvicorn，确保依赖版本正确
    cmd = [
        "uv", "run", "uvicorn", 
        "influflow.api.main:app",
        "--host", "0.0.0.0",
        "--port", port,
        "--reload"
    ]
    
    print(f"📍 API端口: {port}")
    print(f"📖 文档地址: http://localhost:{port}/docs")
    print("=" * 50)
    
    try:
        # uv run会自动处理依赖和路径设置
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ API启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 API服务器已停止")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        sys.exit(1)


def main():
    """主函数，解析命令行参数并启动相应服务"""
    parser = argparse.ArgumentParser(description="InfluFlow Backend 启动脚本")
    parser.add_argument(
        'mode', 
        choices=['ui', 'api'],
        default='ui',
        nargs='?',
        help='启动模式: ui (Streamlit界面), api (FastAPI服务器)'
    )
    
    args = parser.parse_args()
    
    # 设置环境
    setup_environment()
    
    if args.mode == 'api':
        start_api()
    else:  # ui模式
        # 本地UI模式
        print("🚀 启动本地UI...")
        # 使用uv run确保依赖版本正确
        ui_cmd = ["uv", "run", "python", "start_ui.py"]
        try:
            subprocess.run(ui_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ UI启动失败: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n👋 UI已停止")

if __name__ == "__main__":
    main() 