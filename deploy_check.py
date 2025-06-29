#!/usr/bin/env python3
"""
部署检查脚本
用于诊断本地和云端环境差异
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
import json

def check_python_version():
    """检查Python版本"""
    version = platform.python_version()
    print(f"✅ Python版本: {version}")
    return version

def check_environment_variables():
    """检查环境变量"""
    required_vars = ['OPENAI_API_KEY']
    optional_vars = ['PORT', 'TAVILY_API_KEY']
    
    print("\n🔍 环境变量检查:")
    
    missing_required = []
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 10)}...")
        else:
            print(f"❌ {var}: 未设置")
            missing_required.append(var)
    
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            print(f"ℹ️  {var}: {'*' * min(len(value), 10)}...")
        else:
            print(f"⚪ {var}: 未设置（可选）")
    
    return missing_required

def check_dependencies():
    """检查关键依赖版本"""
    print("\n📦 依赖版本检查:")
    
    # 包名映射 (pip包名 -> 导入名)
    packages = {
        'openai': 'openai',
        'langchain-openai': 'langchain_openai', 
        'langsmith': 'langsmith',
        'streamlit': 'streamlit',
        'langchain-community': 'langchain_community',
        'langgraph': 'langgraph'
    }
    
    for pip_name, import_name in packages.items():
        try:
            # 尝试获取版本
            result = subprocess.run(
                [sys.executable, '-c', f'''
try:
    import {import_name}
    try:
        print({import_name}.__version__)
    except AttributeError:
        import pkg_resources
        try:
            print(pkg_resources.get_distribution("{pip_name}").version)
        except:
            print("IMPORTED_NO_VERSION")
except ImportError:
    print("IMPORT_ERROR")
'''],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output == "IMPORT_ERROR":
                    print(f"❌ {pip_name}: 导入失败")
                elif output == "IMPORTED_NO_VERSION":
                    print(f"✅ {pip_name}: 已安装（版本未知）")
                else:
                    print(f"✅ {pip_name}: {output}")
            else:
                print(f"❌ {pip_name}: 检查失败")
        except Exception as e:
            print(f"❌ {pip_name}: 检查失败 - {e}")

def check_openai_api():
    """检查OpenAI API连接"""
    print("\n🌐 OpenAI API连接检查:")
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY 未设置，跳过API测试")
        return False
    
    try:
        # 简单的API测试
        from openai import OpenAI
        client = OpenAI()
        
        # 获取模型列表（轻量级测试）
        models = client.models.list()
        print(f"✅ OpenAI API连接成功，可用模型: {len(models.data)}个")
        return True
        
    except ImportError:
        print("❌ OpenAI包未安装")
        return False
    except Exception as e:
        print(f"❌ OpenAI API连接失败: {e}")
        return False

def check_streamlit_config():
    """检查Streamlit配置"""
    print("\n🎛️  Streamlit配置检查:")
    
    streamlit_config_dirs = [
        Path.home() / '.streamlit',
        Path.cwd() / '.streamlit'
    ]
    
    for config_dir in streamlit_config_dirs:
        if config_dir.exists():
            print(f"✅ 找到Streamlit配置目录: {config_dir}")
            
            config_file = config_dir / 'config.toml'
            if config_file.exists():
                print(f"✅ 找到配置文件: {config_file}")
            else:
                print(f"⚪ 配置文件不存在: {config_file}")
        else:
            print(f"⚪ 配置目录不存在: {config_dir}")

def generate_environment_report():
    """生成环境报告"""
    print("\n📊 生成环境报告...")
    
    report = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "architecture": platform.architecture(),
        "environment_variables": {
            var: "SET" if os.environ.get(var) else "NOT_SET"
            for var in ['OPENAI_API_KEY', 'PORT', 'TAVILY_API_KEY']
        },
        "working_directory": str(Path.cwd()),
        "script_location": str(Path(__file__).parent.absolute())
    }
    
    # 保存到文件
    report_file = Path("environment_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 环境报告已保存到: {report_file}")
    return report

def main():
    """主函数"""
    print("🚀 开始部署环境检查...")
    print("=" * 50)
    
    # 检查各项配置
    python_version = check_python_version()
    missing_vars = check_environment_variables()
    check_dependencies()
    api_ok = check_openai_api()
    check_streamlit_config()
    
    # 总结
    print("\n" + "=" * 50)
    print("📋 检查总结:")
    
    if missing_vars:
        print(f"❌ 缺少必需环境变量: {', '.join(missing_vars)}")
    else:
        print("✅ 所有必需环境变量已设置")
    
    if api_ok:
        print("✅ OpenAI API连接正常")
    else:
        print("❌ OpenAI API连接问题")
    
    # 云端部署建议
    print("\n💡 云端部署建议:")
    print("1. 确保在Railway dashboard中设置所有环境变量")
    print("2. 检查API key余额和速率限制")
    print("3. 查看应用日志排查具体错误")
    print("4. 如果效果不一致，尝试强制重新部署")
    

if __name__ == "__main__":
    main() 