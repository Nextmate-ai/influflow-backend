#!/usr/bin/env python3
"""
优化的启动脚本，适用于云平台部署
支持Railway、Heroku等云平台的环境配置
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

def setup_environment():
    """设置云平台环境"""
    # 优先从.env文件加载环境变量，方便本地开发
    # 在云平台部署时，如果.env文件不存在，则会使用平台设置的环境变量
    load_dotenv()
    
    # 确保在正确的目录
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # 云平台端口配置
    port = os.environ.get('PORT', '8501')
    
    # Streamlit配置
    streamlit_config = {
        'server.port': port,
        'server.address': '0.0.0.0',
        'server.headless': 'true',
        'server.enableCORS': 'false',
        'server.enableXsrfProtection': 'false',
        'browser.gatherUsageStats': 'false',
        'global.dataFrameSerialization': 'legacy'
    }
    
    return port, streamlit_config

def validate_api_keys():
    """验证必需的API密钥"""
    required_keys = ['OPENAI_API_KEY', 'TAVILY_API_KEY']
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

def start_streamlit():
    """启动Streamlit应用"""
    port, config = setup_environment()
    
    # 验证环境
    if not validate_api_keys():
        sys.exit(1)
    
    # 构建启动命令
    ui_file = "src/open_deep_research/ui.py"
    
    if not os.path.exists(ui_file):
        print(f"❌ 找不到UI文件: {ui_file}")
        sys.exit(1)
    
    # Streamlit启动参数
    cmd = [
        sys.executable, "-m", "streamlit", "run", ui_file,
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--browser.gatherUsageStats=false"
    ]
    
    print(f"🚀 启动Open Deep Research UI...")
    print(f"📍 端口: {port}")
    print(f"🌐 地址: 0.0.0.0:{port}")
    print("=" * 50)
    
    try:
        # 启动应用
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_streamlit() 