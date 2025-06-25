#!/bin/bash

# Open Deep Research - Railway部署脚本
# 自动化设置Railway部署环境

set -e

echo "🚀 Open Deep Research Railway部署脚本"
echo "======================================"

# 检查是否安装了Railway CLI
if ! command -v railway &> /dev/null; then
    echo "📦 安装Railway CLI..."
    npm install -g @railway/cli
fi

# 检查登录状态
echo "🔐 检查Railway登录状态..."
if ! railway whoami &> /dev/null; then
    echo "请先登录Railway:"
    railway login
fi

# 创建项目
echo "🏗️  创建Railway项目..."
railway create open-deep-research

# 设置环境变量
echo "⚙️  配置环境变量..."
echo "请依次输入您的API密钥："

read -p "OpenAI API Key: " OPENAI_KEY
railway variables set OPENAI_API_KEY="$OPENAI_KEY"

read -p "Tavily API Key: " TAVILY_KEY
railway variables set TAVILY_API_KEY="$TAVILY_KEY"

read -p "Anthropic API Key (可选，回车跳过): " ANTHROPIC_KEY
if [ -n "$ANTHROPIC_KEY" ]; then
    railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_KEY"
fi

read -p "Perplexity API Key (可选，回车跳过): " PERPLEXITY_KEY
if [ -n "$PERPLEXITY_KEY" ]; then
    railway variables set PERPLEXITY_API_KEY="$PERPLEXITY_KEY"
fi

read -p "Exa API Key (可选，回车跳过): " EXA_KEY
if [ -n "$EXA_KEY" ]; then
    railway variables set EXA_API_KEY="$EXA_KEY"
fi

# 部署应用
echo "🚀 部署应用..."
railway up

echo "✅ 部署完成！"
echo ""
echo "📋 后续步骤："
echo "1. 访问Railway dashboard查看部署状态"
echo "2. 获取应用URL"
echo "3. 测试应用功能"
echo ""
echo "💡 有用的命令："
echo "  railway logs          - 查看应用日志"
echo "  railway logs --build  - 查看构建日志"
echo "  railway status        - 查看项目状态"
echo "  railway delete        - 删除项目" 