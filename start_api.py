#!/usr/bin/env python3
"""
InfluFlow Backend API启动脚本
启动FastAPI服务器，提供Twitter AI功能的HTTP接口
"""

import sys
import os
import subprocess

# uv run会自动处理依赖和路径设置，无需手动添加路径

def main():
    """启动FastAPI应用"""
    print("🚀 Starting InfluFlow AI Backend API...")
    print("📖 API文档将在以下地址提供:")
    print("   - Swagger UI: http://localhost:8000/docs")
    print("   - ReDoc: http://localhost:8000/redoc")
    print("🔗 健康检查: http://localhost:8000/health")
    print("-" * 50)
    
    # 使用uv run启动uvicorn服务器，确保依赖版本正确
    try:
        subprocess.run([
            "uv", "run", "uvicorn",
            "influflow.api.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",  # 开发模式下启用热重载
            "--reload-dir", "src",  # 监控src目录的变化
            "--log-level", "info"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ API启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 API服务器已停止")
    except FileNotFoundError:
        print("❌ 找不到uv命令，请确保已安装uv包管理器")
        print("安装方法: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

if __name__ == "__main__":
    main() 