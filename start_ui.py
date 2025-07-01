#!/usr/bin/env python3
"""
InfluFlow Backend UI启动脚本
启动Streamlit UI，使用服务层架构
"""

import sys
import os
import subprocess

# uv run会自动处理依赖和路径设置，无需手动添加路径

def main():
    """启动Streamlit UI"""
    print("🚀 Starting InfluFlow UI...")
    print("🌐 UI将在以下地址启动:")
    print("   - 本地: http://localhost:8501")
    print("⚡ 当前使用服务层架构，代码更清晰易维护")
    print("-" * 50)
    
    # 使用uv run启动streamlit应用，确保使用正确的依赖版本
    try:
        subprocess.run([
            "uv", "run", "streamlit", "run", 
            "src/influflow/ui.py",
            "--server.port=8501",
            "--server.address=0.0.0.0"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动UI失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 UI已停止")
    except FileNotFoundError:
        print("❌ 找不到uv命令，请确保已安装uv包管理器")
        print("安装方法: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

if __name__ == "__main__":
    main() 