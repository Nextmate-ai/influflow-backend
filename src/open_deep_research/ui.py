"""
Open Deep Research UI
基于Streamlit的用户界面，用于与研究workflow交互
"""

import streamlit as st
import asyncio
import uuid
import time
import re
from typing import Dict, Any, List
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

# Import the builder instead of the compiled graph
from open_deep_research.graph import builder
# 增加styler相关导入
from open_deep_research.styler import convert_text, convert_text_stream, get_supported_tags

# Create a singleton graph with checkpointer for UI usage
# This avoids recompiling the graph for each ResearchUI instance
_ui_graph = None

def get_ui_graph():
    """Get or create the UI graph with in-memory checkpointer (singleton pattern)"""
    global _ui_graph
    if _ui_graph is None:
        memory = MemorySaver()
        _ui_graph = builder.compile(checkpointer=memory)
    return _ui_graph


def safe_asyncio_run(coro):
    """
    安全地在同步环境中运行异步协程，特别是在Streamlit中。
    此函数通过检测现有的事件循环来避免常见错误，并处理取消操作。
    """
    try:
        try:
            # 尝试获取当前线程中正在运行的事件循环
            asyncio.get_running_loop()
            
            # 如果存在正在运行的循环，在一个新线程中运行协程以避免冲突。
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()

        except RuntimeError:
            # 如果没有正在运行的循环（最常见的情况），
            # 使用 asyncio.run() 是最安全的方式。
            return asyncio.run(coro)
            
    except (GeneratorExit, asyncio.CancelledError) as e:
        print(f"Async operation was cancelled: {e}")
        return {"status": "error", "error": "Operation was cancelled by user interface"}
    except Exception as e:
        print(f"Error in async operation: {e}")
        return {"status": "error", "error": f"Async execution error: {str(e)}"}


async def protected_astream(graph, input_data, config, stream_mode="updates"):
    """
    受保护的异步流，防止被Streamlit取消
    使用asyncio.shield来保护关键的异步操作
    """
    try:
        # 使用shield保护异步流不被取消
        async def _run_stream():
            results = []
            async for event in graph.astream(input_data, config, stream_mode=stream_mode):
                results.append(event)
                # 如果找到中断，立即返回
                if '__interrupt__' in event:
                    return results
            return results
        
        # 使用shield保护整个流程
        results = await asyncio.shield(_run_stream())
        return results
        
    except asyncio.CancelledError:
        print("Stream was cancelled, but handling gracefully")
        # 即使被取消，也返回一个有效的响应
        return [{"status": "cancelled", "message": "Stream was cancelled by UI"}]
    except GeneratorExit:
        print("Stream generator exited, handling gracefully")
        return [{"status": "generator_exit", "message": "Stream generator was closed"}]
    except Exception as e:
        print(f"Error in protected stream: {e}")
        return [{"status": "error", "message": f"Stream error: {str(e)}"}]


async def protected_styler_stream(original_text, tag, config, custom_prompt="", reference_text=""):
    """
    受保护的styler流式转换，防止被Streamlit取消
    """
    try:
        # 使用shield保护异步流不被取消
        async def _run_styler_stream():
            full_text = ""
            async for chunk in convert_text_stream(original_text, tag, config, custom_prompt, reference_text):
                full_text += chunk
                yield full_text
        
        # 使用shield保护整个流程
        async for result in asyncio.shield(_run_styler_stream()):
            yield result
            
    except asyncio.CancelledError:
        print("Styler stream was cancelled, but handling gracefully")
        yield "转换被取消"
    except GeneratorExit:
        print("Styler stream generator exited, handling gracefully")
        yield "转换流程结束"
    except Exception as e:
        print(f"Error in styler stream: {e}")
        yield f"转换错误: {str(e)}"


def format_sections_structure_for_display(structure_text: str) -> str:
    """
    格式化章节结构文本，生成正确的分层编号格式
    """
    if not structure_text:
        return "无章节结构信息"

    lines = structure_text.split('\n')
    formatted_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        
        # 仅保留包含标题的行
        if "Description:" in stripped_line or \
           "Research needed:" in stripped_line or \
           "Status:" in stripped_line or \
           "Content preview:" in stripped_line:
            continue

        # 保留原始缩进来确定层级
        leading_spaces = len(line) - len(line.lstrip(' '))
        indent_level = leading_spaces // 2  # 每2个空格为一个缩进级别
        
        # 移除行号前缀，提取标题
        cleaned_line = re.sub(r'^\d+\.\s+', '', stripped_line)
        
        # 根据缩进级别添加适当的空格（子章节缩进4个空格）
        if indent_level > 0:
            indent = "    " * indent_level
            formatted_lines.append(f"{indent}{cleaned_line}")
        else:
            formatted_lines.append(cleaned_line)

    return '\n'.join(formatted_lines)


@st.dialog("📋 最终确认研究计划")
def show_final_confirmation_dialog():
    """显示最终确认弹窗"""
    st.markdown("**请最后确认一下研究计划，确认无误后将开始生成报告。**")
    st.markdown("---")
    
    # 获取并显示章节详情
    try:
        if hasattr(st.session_state.ui, 'current_config') and st.session_state.ui.current_config:
            graph_state = st.session_state.ui.graph.get_state(st.session_state.ui.current_config)
            if graph_state and graph_state.values and 'sections' in graph_state.values:
                sections = graph_state.values['sections']
                
                def format_section_outline(sections_list, parent_num="", indent_level=0):
                    """递归格式化章节大纲，生成正确的编号和缩进格式"""
                    outline_lines = []
                    
                    for i, section in enumerate(sections_list, 1):
                        # 生成章节编号
                        if parent_num:
                            section_num = f"{parent_num}.{i}"
                        else:
                            section_num = str(i)
                        
                        # 格式化标题
                        title = section.name
                        
                        # 根据缩进级别添加空格（子章节缩进4个空格）
                        if indent_level > 0:
                            indent = "    " * indent_level
                            line = f"{indent}{section_num}. {title}"
                        else:
                            line = f"{section_num}. {title}"
                        
                        outline_lines.append(line)
                        
                        # 如果有子章节，递归处理
                        if hasattr(section, 'sections') and section.sections:
                            sub_outline = format_section_outline(section.sections, section_num, indent_level + 1)
                            outline_lines.extend(sub_outline)
                    
                    return outline_lines
                
                # 生成大纲
                outline_lines = format_section_outline(sections)
                outline_text = '\n'.join(outline_lines)
                
                # 在固定高度容器中显示
                st.subheader("📚 研究计划大纲")
                with st.container(height=300, border=True):
                    if outline_text:
                        st.code(outline_text, language="text")
                    else:
                        st.info("暂无章节信息")
            else:
                st.warning("无法获取章节详情")
        else:
            st.warning("无法获取当前配置")
    except Exception as e:
        st.error(f"显示章节详情时出错: {str(e)}")
    
    st.markdown("---")
    
    # 确认按钮
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("❌ 取消", use_container_width=True):
            st.session_state.show_final_confirmation = False
            st.rerun()
    
    with col2:
        if st.button("🔙 修改计划", use_container_width=True):
            st.session_state.show_final_confirmation = False
            st.rerun()
    
    with col3:
        if st.button("✅ 确认开始", type="primary", use_container_width=True):
            # 关闭弹窗并开始生成报告
            st.session_state.show_final_confirmation = False
            st.session_state.workflow_running = True
            st.session_state.workflow_progress = []
            st.rerun()


class ResearchUI:
    """研究助手用户界面"""
    
    def __init__(self):
        """初始化UI组件"""
        # Use singleton graph with checkpointer for UI
        # This avoids recompiling the graph for each instance
        self.graph = get_ui_graph()
        self.current_config = None  # 保存当前配置用于继续workflow
        self._session_active = False  # 添加session状态追踪
        
    def get_default_config(self, planner_model: str = "gpt-4o-mini", writer_model: str = "gpt-4o-mini", search_max_results: int = 2, thread_id: str = None) -> Dict[str, Any]:
        """获取默认配置"""
        # 如果没有提供thread_id，生成一个新的
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            
        return {
            "configurable": {
                "thread_id": thread_id,
                "search_api": "tavily",
                "planner_provider": "openai", 
                "planner_model": planner_model,
                "writer_provider": "openai",
                "writer_model": writer_model,
                "max_search_depth": 1,
                "number_of_queries": 2,
                "process_search_results": "split_and_rerank",
                "search_api_config": {"max_results": search_max_results}
            }
        }
    
    def reset_session(self):
        """重置session状态"""
        self._session_active = False
        self.current_config = None
        
    async def run_research_workflow(self, topic: str, local_sources: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
        """运行研究workflow"""
        try:
            # 设置session为活跃状态
            self._session_active = True
            # 保存配置用于后续使用
            self.current_config = config
            
            # 第一步：启动workflow并等待human feedback
            input_data = {"topic": topic}
            if local_sources:
                input_data["local_sources"] = local_sources
                
            # 使用受保护的异步流
            events = await protected_astream(self.graph, input_data, config)
            
            # 检查session是否仍然活跃
            if not self._session_active:
                return {"status": "error", "error": "Session was reset during execution"}
            
            # 处理事件
            interrupt_value = None
            for event in events:
                if isinstance(event, dict):
                    if '__interrupt__' in event:
                        interrupt_value = event['__interrupt__'][0].value
                        break
                    elif event.get("status") in ["cancelled", "generator_exit", "error"]:
                        return {"status": "error", "error": event.get("message", "Stream error")}
                        
            return {"status": "waiting_feedback", "interrupt_message": interrupt_value}
            
        except Exception as e:
            self._session_active = False
            return {"status": "error", "error": str(e)}
    
    async def continue_with_feedback(self, feedback: Any, return_progress: bool = False) -> Dict[str, Any]:
        """使用用户反馈继续workflow"""
        try:
            # 使用保存的配置
            if not self.current_config or not self._session_active:
                return {"status": "error", "error": "No active workflow session found"}
            
            # 使用受保护的异步流继续workflow
            events = await protected_astream(self.graph, Command(resume=feedback), self.current_config)
            
            # 检查session是否仍然活跃
            if not self._session_active:
                return {"status": "error", "error": "Session was reset during execution"}
            
            # 处理事件和进度
            interrupt_value = None
            progress_events = []
            
            for event in events:
                if isinstance(event, dict):
                    # 检查错误状态
                    if event.get("status") in ["cancelled", "generator_exit", "error"]:
                        return {"status": "error", "error": event.get("message", "Stream error")}
                    
                    # 如果需要返回进度信息
                    if return_progress:
                        # 收集进度事件
                        for node_name, node_data in event.items():
                            if node_name not in ['__interrupt__', 'status', 'message']:
                                progress_events.append({
                                    "node": node_name,
                                    "timestamp": time.time(),
                                    "data": str(node_data) if node_data else "Processing..."
                                })
                    
                    # 检查是否有新的中断（包括章节调整中断）
                    if '__interrupt__' in event:
                        interrupt_value = event['__interrupt__'][0].value
                        # 检查是否是章节调整中断
                        if "Current Report Structure:" in interrupt_value:
                            return {
                                "status": "waiting_section_adjustment", 
                                "interrupt_message": interrupt_value,
                                "progress": progress_events if return_progress else None
                            }
                        else:
                            return {
                                "status": "waiting_feedback", 
                                "interrupt_message": interrupt_value,
                                "progress": progress_events if return_progress else None
                            }
                
            # 如果没有中断，说明workflow完成了
            # 获取最终状态
            try:
                final_state = self.graph.get_state(self.current_config)
                
                if final_state and final_state.values:
                    final_report = final_state.values.get('final_report', "No report generated")
                    # 注意：不要设置 self._session_active = False，保持session活跃状态
                    # 只有在真正结束时才设置为False
                    return {
                        "status": "completed",
                        "report": final_report,
                        "sections": final_state.values.get('sections', []),
                        "progress": progress_events if return_progress else None
                    }
                else:
                    return {"status": "error", "error": "No final state found"}
            except Exception as e:
                return {"status": "error", "error": f"Failed to get final state: {str(e)}"}
                
        except Exception as e:
            self._session_active = False
            return {"status": "error", "error": str(e)}

    async def continue_with_section_adjustment(self, adjustments: Any) -> Dict[str, Any]:
        """处理章节调整并继续workflow"""
        try:
            # 使用保存的配置
            if not self.current_config or not self._session_active:
                return {"status": "error", "error": "No active workflow session found"}
            
            # 使用受保护的异步流继续workflow
            events = await protected_astream(self.graph, Command(resume=adjustments), self.current_config)
            
            # 检查session是否仍然活跃
            if not self._session_active:
                return {"status": "error", "error": "Session was reset during execution"}
            
            # 处理事件
            interrupt_value = None
            for event in events:
                if isinstance(event, dict):
                    # 检查错误状态
                    if event.get("status") in ["cancelled", "generator_exit", "error"]:
                        return {"status": "error", "error": event.get("message", "Stream error")}
                    
                    # 检查是否有新的中断（章节调整后可能再次需要调整）
                    if '__interrupt__' in event:
                        interrupt_value = event['__interrupt__'][0].value
                        if "Current Report Structure:" in interrupt_value:
                            return {
                                "status": "waiting_section_adjustment", 
                                "interrupt_message": interrupt_value
                            }
                        else:
                            return {
                                "status": "waiting_feedback", 
                                "interrupt_message": interrupt_value
                            }
                
            # 如果没有中断，说明workflow完成了
            # 获取最终状态
            try:
                final_state = self.graph.get_state(self.current_config)
                
                if final_state and final_state.values:
                    final_report = final_state.values.get('final_report', "No report generated")
                    # 注意：不要设置 self._session_active = False，保持session活跃状态
                    # 只有在真正结束时才设置为False
                    return {
                        "status": "completed",
                        "report": final_report,
                        "sections": final_state.values.get('sections', [])
                    }
                else:
                    return {"status": "error", "error": "No final state found"}
            except Exception as e:
                return {"status": "error", "error": f"Failed to get final state: {str(e)}"}
                
        except Exception as e:
            self._session_active = False
            return {"status": "error", "error": str(e)}


def main():
    """主函数：构建Streamlit界面"""
    st.set_page_config(
        page_title="Open Deep Research Assistant",
        page_icon="🔬",
        layout="wide"
    )
    
    st.title("🔬 Open Deep Research Assistant")
    st.markdown("---")
    
    # 初始化session state
    if 'ui' not in st.session_state:
        st.session_state.ui = ResearchUI()
        st.session_state.workflow_started = False
        st.session_state.config = None
        st.session_state.waiting_feedback = False
        st.session_state.interrupt_message = None
        st.session_state.completed = False
        st.session_state.final_report = None
        st.session_state.sections = None
        # 增加styler相关状态
        st.session_state.styled_reports = {}  # 存储不同风格的报告 {tag: styled_text}
        st.session_state.current_style_tag = "原始版本"  # 当前显示的风格
        # 增加章节调整相关状态
        st.session_state.waiting_section_adjustment = False  # 是否等待章节调整
        st.session_state.section_adjustment_message = None  # 章节调整消息
        # 初始化thread_id以避免重复生成
        st.session_state.thread_id = str(uuid.uuid4())

    # 确保必要的属性已初始化（防止页面刷新后丢失）
    if 'final_report' not in st.session_state:
        st.session_state.final_report = None
    if 'styled_reports' not in st.session_state:
        st.session_state.styled_reports = {}
    if 'current_style_tag' not in st.session_state:
        st.session_state.current_style_tag = "原始版本"
    if 'show_final_confirmation' not in st.session_state:
        st.session_state.show_final_confirmation = False
    if 'workflow_running' not in st.session_state:
        st.session_state.workflow_running = False
    if 'workflow_progress' not in st.session_state:
        st.session_state.workflow_progress = []
    if 'waiting_section_adjustment' not in st.session_state:
        st.session_state.waiting_section_adjustment = False
    if 'section_adjustment_message' not in st.session_state:
        st.session_state.section_adjustment_message = None
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    
    # 左侧边栏：模型选择
    with st.sidebar:
        st.header("⚙️ 模型配置")
        
        # 分别选择planner和writer模型
        available_models = ["gpt-4.1-mini", "gpt-4o-mini", "o3-mini", "gpt-4.1", "gpt-4o"]
        
        st.subheader("🧠 规划模型 (Planner)")
        planner_model = st.selectbox(
            "负责生成报告结构和评估内容质量",
            available_models,
            index=0,  # 默认选择gpt-4.1-mini
            key="planner_model",
            help="规划模型负责：报告大纲规划、章节质量评估、反思改进等任务"
        )
        
        st.subheader("✍️ 写作模型 (Writer)")
        writer_model = st.selectbox(
            "负责生成搜索查询和写作内容",
            available_models,
            index=0,  # 默认选择gpt-4.1-mini
            key="writer_model", 
            help="写作模型负责：搜索查询生成、章节内容写作、文本润色等任务"
        )
        
        st.subheader("🔍 每次网络搜索的资料数量")
        search_max_results = st.number_input(
            "每次网络搜索的资料数量",
            min_value=1,
            max_value=10,
            value=5,
            key="search_max_results",
            help="每次网络搜索的资料数量"
        )
        
        st.subheader("🎨 风格转换模型 (Styler)")
        styler_model = st.selectbox(
            "负责文本风格转换和改写",
            available_models,
            index=0,  # 默认选择gpt-4.1-mini
            key="styler_model",
            help="风格转换模型负责：文本风格改写、体裁转换、语言润色等任务"
        )
        
        # 显示当前配置信息
        st.markdown("---")
        st.markdown("**当前配置:**")
        st.markdown(f"- 📋 规划模型: {planner_model}")
        st.markdown(f"- ✍️ 写作模型: {writer_model}")
        st.markdown(f"- 🎨 风格模型: {styler_model}")
        st.markdown("- 🔍 搜索API: Tavily") 
        st.markdown("- 🔄 搜索深度: 1轮")
        st.markdown("- 📊 查询数: 2个/轮")
        
        # Temperature显示
        st.markdown("**模型参数:**")
        st.markdown("- 📋 规划温度: 0.2 (低随机性)")
        st.markdown("- ✍️ 写作温度: 0.5 (平衡性)")
        st.markdown("- 🎨 风格温度: 0.5 (创意平衡)")
        
        # 生成配置，但只有在没有活跃workflow时才更新thread_id
        if not st.session_state.workflow_started or st.session_state.completed:
            # 可以更新配置，但保持thread_id不变（除非重新开始）
            st.session_state.config = st.session_state.ui.get_default_config(
                planner_model, writer_model, search_max_results, st.session_state.thread_id
            )
        else:
            # workflow进行中，不更新配置，显示当前状态
            if st.session_state.config:
                st.info("🔄 研究进行中，模型配置已锁定")
            else:
                # 如果config不存在，使用当前设置创建
                st.session_state.config = st.session_state.ui.get_default_config(
                    planner_model, writer_model, search_max_results, st.session_state.thread_id
                )
    
    # 主界面
    if not st.session_state.workflow_started:
        # 步骤1：初始输入
        st.header("📝 开始新的研究")
        
        # 本地知识源管理区域（在form外面）
        st.subheader("📚 本地知识源管理（可选）")
        st.markdown("*添加您的本地知识内容，如文档片段、研究笔记、专业见解等*")
        
        # 初始化session state中的local sources
        if 'local_sources_list' not in st.session_state:
            st.session_state.local_sources_list = []
        
        # 添加新源的按钮
        if st.button("➕ 添加知识源", type="primary"):
            st.session_state.local_sources_list.append({
                'id': len(st.session_state.local_sources_list),
                'title': f"知识源 {len(st.session_state.local_sources_list) + 1}",
                'content': ""
            })
            st.rerun()
        
        # 显示已添加的源
        if st.session_state.local_sources_list:
            st.markdown("---")
            st.markdown("**已添加的知识源：**")
            
            sources_to_remove = []
            
            for i, source in enumerate(st.session_state.local_sources_list):
                with st.expander(f"📄 {source['title']}", expanded=True):
                    # 源标题编辑
                    col_title, col_delete = st.columns([4, 1])
                    with col_title:
                        new_title = st.text_input(
                            "知识源标题:",
                            value=source['title'],
                            key=f"title_{source['id']}",
                            placeholder="例如：相关研究论文摘要"
                        )
                        source['title'] = new_title
                    
                    with col_delete:
                        st.markdown("<br>", unsafe_allow_html=True)  # 对齐按钮
                        if st.button("🗑️", key=f"delete_{source['id']}", help="删除此知识源"):
                            sources_to_remove.append(i)
                            st.rerun()
                    
                    # 内容编辑
                    source['content'] = st.text_area(
                        "知识源内容 (支持Markdown格式):",
                        value=source['content'],
                        height=120,
                        key=f"content_{source['id']}",
                        placeholder="""例如：
## 研究背景
根据Smith等人(2023)的研究，人工智能在医疗诊断中的准确率已达到95%...

**关键发现：**
- 深度学习模型在影像识别方面表现优异
- 需要大量标注数据进行训练
- 存在数据隐私和伦理问题

*参考文献：Smith, J. et al. (2023). AI in Healthcare Diagnostics.*""",
                        help="支持Markdown语法：**粗体**、*斜体*、## 标题、- 列表等"
                    )
                    
                    # 内容预览
                    if source['content'].strip():
                        st.markdown("**📝 预览效果：**")
                        try:
                            st.markdown(source['content'])
                        except Exception:
                            st.caption("*预览渲染中...*")
            
            # 删除标记的源
            for index in reversed(sources_to_remove):
                st.session_state.local_sources_list.pop(index)
            
            # 清空所有按钮
            if len(st.session_state.local_sources_list) > 1:
                col_clear, col_export, col_summary = st.columns([1, 1, 2])
                with col_clear:
                    if st.button("🗑️ 清空所有", type="secondary"):
                        st.session_state.local_sources_list = []
                        st.rerun()
                
                with col_export:
                    # 准备导出数据
                    import json
                    export_data = [
                        {'title': source['title'], 'content': source['content']}
                        for source in st.session_state.local_sources_list
                    ]
                    export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
                    
                    st.download_button(
                        label="💾 导出知识源",
                        data=export_json,
                        file_name="local_sources.json",
                        mime="application/json",
                        help="导出为JSON格式，可以后续导入"
                    )
                
                with col_summary:
                    total_chars = sum(len(source['content']) for source in st.session_state.local_sources_list)
                    st.caption(f"📊 总计：{len(st.session_state.local_sources_list)} 个知识源，约 {total_chars} 字符")
        
        # 主题输入和提交区域
        st.markdown("---")
        with st.form("research_input"):
            st.subheader("🎯 研究主题")
            topic = st.text_area(
                "请输入您想要研究的主题:", 
                height=100,
                placeholder="例如：人工智能在医疗领域的应用现状与未来发展趋势"
            )
            
            # 修改表单提交逻辑，使用新的数据结构
            submitted = st.form_submit_button("🚀 开始研究", type="primary")
            
            if submitted and topic.strip():
                # 从session state中获取本地知识源
                local_sources = []
                if st.session_state.local_sources_list:
                    local_sources = [
                        f"## {source['title']}\n\n{source['content']}" 
                        for source in st.session_state.local_sources_list 
                        if source['content'].strip()
                    ]
                
                # 启动workflow
                with st.spinner("正在生成研究计划..."):
                    try:
                        result = safe_asyncio_run(st.session_state.ui.run_research_workflow(
                            topic, local_sources, st.session_state.config
                        ))
                        
                        if result["status"] == "waiting_feedback":
                            st.session_state.workflow_started = True
                            st.session_state.waiting_feedback = True
                            st.session_state.interrupt_message = result["interrupt_message"]
                            st.rerun()
                        else:
                            st.error(f"启动workflow失败: {result.get('error', '未知错误')}")
                            
                    except Exception as e:
                        st.error(f"执行过程中出现错误: {str(e)}")
            
            elif submitted:
                st.warning("请输入研究主题")
    
    elif st.session_state.waiting_feedback:
        # 步骤2：显示计划并获取反馈
        st.header("📋 研究计划")
        
        # 添加进度指示器
        progress_col1, progress_col2, progress_col3 = st.columns(3)
        with progress_col1:
            st.success("✅ 1. 生成计划")
        with progress_col2:
            st.info("🔄 2. 计划确认中")
        with progress_col3:
            st.empty()
            st.markdown("⏳ 3. 生成报告")
        
        st.markdown("---")
        
        if st.session_state.interrupt_message:
            # 解析interrupt_message，分离sections和mindmap
            def parse_interrupt_message(interrupt_message: str):
                """解析中断消息，分离sections信息和mindmap"""
                lines = interrupt_message.split('\n')
                sections_lines = []
                mindmap_lines = []
                in_mindmap = False
                
                for line in lines:
                    if line.strip().startswith('```mermaid') or 'mindmap' in line.lower():
                        in_mindmap = True
                        mindmap_lines.append(line)
                    elif in_mindmap:
                        mindmap_lines.append(line)
                    elif 'Section:' in line or 'Description:' in line or 'Research needed:' in line or 'Subsections:' in line:
                        sections_lines.append(line)
                    elif line.strip() and not line.startswith('Please provide feedback'):
                        if not in_mindmap:
                            sections_lines.append(line)
                
                return '\n'.join(sections_lines), '\n'.join(mindmap_lines)
            
            def format_sections_display(sections_text: str):
                """以简洁大纲格式显示章节详情"""
                try:
                    # 从graph state获取sections数据
                    if hasattr(st.session_state.ui, 'current_config') and st.session_state.ui.current_config:
                        graph_state = st.session_state.ui.graph.get_state(st.session_state.ui.current_config)
                        if graph_state and graph_state.values and 'sections' in graph_state.values:
                            sections = graph_state.values['sections']
                            
                            def format_section_outline(sections_list, parent_num="", indent_level=0):
                                """递归格式化章节大纲，生成正确的编号格式"""
                                outline_lines = []
                                
                                for i, section in enumerate(sections_list, 1):
                                    # 生成章节编号
                                    if parent_num:
                                        section_num = f"{parent_num}.{i}"
                                    else:
                                        section_num = str(i)
                                    
                                    # 格式化标题
                                    title = section.name
                                    
                                    # 根据缩进级别添加空格（子章节缩进4个空格）
                                    if indent_level > 0:
                                        indent = "    " * indent_level
                                        line = f"{indent}{section_num}. {title}"
                                    else:
                                        line = f"{section_num}. {title}"
                                    
                                    outline_lines.append(line)
                                    
                                    # 如果有子章节，递归处理
                                    if hasattr(section, 'sections') and section.sections:
                                        sub_outline = format_section_outline(section.sections, section_num, indent_level + 1)
                                        outline_lines.extend(sub_outline)
                                
                                return outline_lines
                            
                            # 生成大纲
                            outline_lines = format_section_outline(sections)
                            outline_text = '\n'.join(outline_lines)
                            
                            # 在固定高度容器中显示
                            with st.container(height=400):
                                if outline_text:
                                    st.code(outline_text, language="text")
                                else:
                                    st.info("暂无章节信息")
                            return
                    
                    # 如果无法获取sections对象，显示提示
                    st.info("无法获取sections数据")
                    
                except Exception as e:
                    st.error(f"显示sections数据时出错: {str(e)}")
                    # 备用方案：显示原始文本
                    if sections_text:
                        st.code(sections_text, language="text", height=400)
            
            def generate_text_outline(sections_text: str) -> str:
                """生成简化的文本大纲，支持多级缩进"""
                if not sections_text:
                    return ""
                
                outline_lines = []
                for line in sections_text.split('\n'):
                    original_line = line
                    line = line.strip()
                    
                    if line.startswith('Section:'):
                        # 计算缩进级别
                        leading_spaces = len(original_line) - len(original_line.lstrip())
                        indent_level = leading_spaces // 2  # 每2个空格为一个缩进级别
                        
                        section_name = line.split('Section:', 1)[1].strip()
                        
                        # 生成对应级别的缩进（每级4个空格）
                        indent = "    " * indent_level
                        outline_lines.append(f"{indent}- {section_name}")
                
                return '\n'.join(outline_lines)
            
            # 解析消息
            sections_text, mindmap_text = parse_interrupt_message(st.session_state.interrupt_message)
            
            # 创建两列布局展示计划
            col_section, col_outline = st.columns([3, 2])
            
            with col_section:
                st.subheader("📚 章节数据")
                format_sections_display(sections_text)
            
            with col_outline:
                st.subheader("🗺️ 研究大纲")
                
                # 创建固定高度的容器
                with st.container(height=400):
                    # 生成文本大纲
                    text_outline = generate_text_outline(sections_text)
                    
                    if text_outline:
                        st.markdown("**文本大纲：**")
                        st.markdown(text_outline)
                    else:
                        st.info("暂无大纲信息")
                    
                    # 显示mindmap（如果有的话）
                    if mindmap_text.strip():
                        st.markdown("---")
                        st.markdown("**可视化大纲：**")
                        try:
                            st.markdown(mindmap_text)
                        except Exception:
                            st.info("🔄 大纲生成中...")
            
            # 反馈区域
            st.markdown("---")
            st.subheader("💬 您的反馈")
            
            st.info("💡 **反馈处理流程说明：**\n"
                   "- 提供反馈后，系统将重新生成研究计划\n"
                   "- 您将看到更新后的计划，并可以再次提供反馈或同意执行\n"
                   "- 这个过程可以重复进行，直到您满意为止")
            
            # 创建反馈输入和操作的布局
            col_feedback, col_actions = st.columns([3, 1])
            
            with col_feedback:
                st.markdown("**请提供您的反馈意见** *(支持Markdown格式)*")
                st.caption("💡 您可以使用Markdown格式来结构化您的反馈，例如列表、标题等")
                
                # 使用文本大纲作为默认反馈内容
                text_outline = generate_text_outline(sections_text)
                default_feedback = text_outline if text_outline else "请在此编辑您的研究计划反馈..."
                
                feedback_text = st.text_area(
                    "反馈内容（预填充了当前计划大纲，您可以直接编辑）:",
                    value=default_feedback,
                    height=200,
                    placeholder="""例如：
- Introduction
- Basic Concepts 
- Technical Challenges
- Real-world Applications
- Conclusion""",
                    help="支持Markdown语法：**粗体**、*斜体*、- 列表、## 标题 等。已预填充当前计划，您可以直接修改"
                )
                

                
                # 提交反馈按钮
                st.markdown("---")
                if st.button("📝 提交修改后的计划", type="secondary", use_container_width=True):
                    # 检查用户是否修改了预填充的内容
                    if feedback_text.strip() and feedback_text.strip() != default_feedback.strip():
                        feedback = feedback_text.strip()
                        spinner_text = "正在根据反馈重新生成计划..."
                    elif feedback_text.strip() == default_feedback.strip():
                        # 用户没有修改预填充的内容，视为同意当前计划
                        feedback = True
                        spinner_text = "正在生成报告..."
                    else:
                        # 用户删除了所有内容，视为同意当前计划
                        feedback = True
                        spinner_text = "正在生成报告..."
                        
                    with st.spinner(spinner_text):
                        try:
                            result = safe_asyncio_run(st.session_state.ui.continue_with_feedback(feedback))
                            
                            if result.get("status") == "completed":
                                st.session_state.completed = True
                                st.session_state.final_report = result.get("report")
                                st.session_state.sections = result.get("sections")
                                st.session_state.waiting_feedback = False
                                st.rerun()
                            elif result["status"] == "waiting_feedback":
                                # 重新生成计划后需要再次确认
                                st.session_state.interrupt_message = result["interrupt_message"]
                                st.rerun()
                            else:
                                st.error(f"处理反馈失败: {result.get('error', '未知错误')}")
                        except Exception as e:
                            st.error(f"执行过程中出现错误: {str(e)}")
            
            with col_actions:
                st.markdown("**操作选项**")
                st.markdown("---")
                
                st.markdown("**选项 1: 直接同意**")
                if st.button("✅ 同意当前计划", type="primary"):
                    # 显示最终确认弹窗
                    st.session_state.show_final_confirmation = True
                    st.rerun()
                
                # 显示最终确认弹窗
                if st.session_state.get('show_final_confirmation', False):
                    show_final_confirmation_dialog()
                
                # 显示workflow运行状态
                if st.session_state.get('workflow_running', False):
                    st.markdown("---")
                    st.markdown("### 🔄 报告生成进行中...")
                    
                    # 创建进度显示容器
                    progress_container = st.container()
                    
                    with progress_container:
                        # 显示spinner和当前状态
                        with st.spinner("正在生成研究报告..."):
                            try:
                                feedback = True
                                result = safe_asyncio_run(st.session_state.ui.continue_with_feedback(feedback, return_progress=True))
                                
                                # 显示进度信息
                                if result.get("progress"):
                                    st.markdown("**执行进度：**")
                                    progress_data = result["progress"]
                                    
                                    # 显示最近的几个步骤
                                    recent_steps = progress_data[-5:] if len(progress_data) > 5 else progress_data
                                    
                                    for i, step in enumerate(recent_steps):
                                        node_name = step["node"]
                                        # 美化节点名称显示
                                        node_display = {
                                            "generate_queries": "🔍 生成搜索查询",
                                            "search_web": "🌐 执行网络搜索", 
                                            "write_section": "✍️ 编写章节内容",
                                            "build_section_with_web_research": "📚 构建研究章节",
                                            "gather_completed_sections": "📄 收集完成章节",
                                            "write_final_sections": "📝 编写最终章节",
                                            "compile_final_report": "📋 编译最终报告"
                                        }.get(node_name, f"⚙️ {node_name}")
                                        
                                        if i == len(recent_steps) - 1:
                                            st.success(f"**当前阶段：** {node_display}")
                                        else:
                                            st.info(f"✅ {node_display}")
                                    
                                    # 显示总进度
                                    total_steps = len(progress_data)
                                    st.progress(min(total_steps / 10, 1.0))  # 假设大约10个主要步骤
                                    st.caption(f"已完成 {total_steps} 个处理步骤")
                                
                                # 检查是否完成或需要章节调整
                                if result["status"] == "completed":
                                    st.session_state.workflow_running = False
                                    st.session_state.waiting_feedback = False
                                    st.session_state.completed = True
                                    st.session_state.final_report = result["report"]
                                    st.session_state.sections = result.get("sections")
                                    st.success("✅ 报告生成完成！")
                                    # 移除time.sleep，避免Streamlit中的作用域问题
                                    st.rerun()
                                elif result["status"] == "waiting_section_adjustment":
                                    # 进入章节调整阶段
                                    st.session_state.workflow_running = False
                                    st.session_state.waiting_feedback = False
                                    st.session_state.waiting_section_adjustment = True
                                    st.session_state.section_adjustment_message = result["interrupt_message"]
                                    st.success("✅ 初步报告生成完成！现在可以调整章节结构。")
                                    st.rerun()
                                elif result["status"] == "waiting_feedback":
                                    # 重新生成计划后需要再次确认
                                    st.session_state.workflow_running = False
                                    st.session_state.interrupt_message = result["interrupt_message"]
                                    st.rerun()
                                else:
                                    st.session_state.workflow_running = False
                                    st.error(f"生成报告失败: {result.get('error', '未知错误')}")
                                    
                            except Exception as e:
                                st.session_state.workflow_running = False
                                st.error(f"执行过程中出现错误: {str(e)}")
                    
                    # 添加取消按钮
                    if st.button("❌ 取消生成", type="secondary"):
                        st.session_state.workflow_running = False
                        st.rerun()
                
                st.markdown("**选项 2: 修改后提交**")
                st.caption("修改左侧文本框中的计划，然后点击下方按钮")
    
    elif st.session_state.waiting_section_adjustment:
        # 步骤2.5：章节调整界面
        st.header("📝 章节结构调整")
        
        # 添加进度指示器
        progress_col1, progress_col2, progress_col3, progress_col4 = st.columns(4)
        with progress_col1:
            st.success("✅ 1. 生成计划")
        with progress_col2:
            st.success("✅ 2. 生成报告")
        with progress_col3:
            st.info("🔄 3. 调整章节")
        with progress_col4:
            st.empty()
            st.markdown("⏳ 4. 风格转换")
        
        st.markdown("---")
        
        # 创建章节调整界面
        if st.session_state.section_adjustment_message:
            # 解析章节调整消息
            adjustment_message = st.session_state.section_adjustment_message
            
            # 提取当前报告结构和报告预览
            lines = adjustment_message.split('\n')
            structure_lines = []
            preview_lines = []
            in_structure = False
            in_preview = False
            
            for line in lines:
                if "Current Report Structure:" in line:
                    in_structure = True
                    in_preview = False
                    continue
                elif "Current Report Preview:" in line:
                    in_structure = False
                    in_preview = True
                    continue
                elif "You can now adjust" in line:
                    break
                    
                if in_structure and line.strip():
                    structure_lines.append(line)
                elif in_preview and line.strip():
                    preview_lines.append(line)
            
            current_structure = '\n'.join(structure_lines)
            current_preview = '\n'.join(preview_lines)
            
            # 创建两列布局
            col_structure, col_adjustment = st.columns([3, 2])
            
            with col_structure:
                st.subheader("📋 当前报告结构")
                
                # 显示当前章节结构
                with st.container(height=300, border=True):
                    # 尝试直接从graph state获取sections对象进行格式化
                    try:
                        if hasattr(st.session_state.ui, 'current_config') and st.session_state.ui.current_config:
                            graph_state = st.session_state.ui.graph.get_state(st.session_state.ui.current_config)
                            if graph_state and graph_state.values and 'sections' in graph_state.values:
                                sections = graph_state.values['sections']
                                
                                def format_section_outline(sections_list, parent_num="", indent_level=0):
                                    """递归格式化章节大纲，生成正确的编号和缩进格式"""
                                    outline_lines = []
                                    
                                    for i, section in enumerate(sections_list, 1):
                                        # 生成章节编号
                                        if parent_num:
                                            section_num = f"{parent_num}.{i}"
                                        else:
                                            section_num = str(i)
                                        
                                        # 格式化标题
                                        title = section.name
                                        
                                        # 根据缩进级别添加空格（子章节缩进4个空格）
                                        if indent_level > 0:
                                            indent = "    " * indent_level
                                            line = f"{indent}{section_num}. {title}"
                                        else:
                                            line = f"{section_num}. {title}"
                                        
                                        outline_lines.append(line)
                                        
                                        # 如果有子章节，递归处理
                                        if hasattr(section, 'sections') and section.sections:
                                            sub_outline = format_section_outline(section.sections, section_num, indent_level + 1)
                                            outline_lines.extend(sub_outline)
                                    
                                    return outline_lines
                                
                                # 生成大纲
                                outline_lines = format_section_outline(sections)
                                outline_text = '\n'.join(outline_lines)
                                
                                if outline_text:
                                    st.code(outline_text, language="text")
                                else:
                                    st.info("暂无章节信息")
                            else:
                                # 备用方案：使用原来的text parsing方法
                                if current_structure:
                                    formatted_structure = format_sections_structure_for_display(current_structure)
                                    st.code(formatted_structure, language="text")
                                else:
                                    st.info("无法获取章节结构")
                        else:
                            st.info("无法获取当前配置")
                    except Exception as e:
                        st.caption(f"显示章节结构时出错: {str(e)}")
                        # 备用方案：使用原来的text parsing方法
                        if current_structure:
                            formatted_structure = format_sections_structure_for_display(current_structure)
                            st.code(formatted_structure, language="text")
                        else:
                            st.info("无法获取章节结构")
                
                # 将报告预览放在一个可展开的容器中
                with st.expander("📄 完整报告预览", expanded=True):
                    # 尝试获取完整的报告内容
                    full_report = None
                    try:
                        if hasattr(st.session_state.ui, 'current_config') and st.session_state.ui.current_config:
                            graph_state = st.session_state.ui.graph.get_state(st.session_state.ui.current_config)
                            if graph_state and graph_state.values:
                                # 优先获取final_report，如果没有则尝试获取其他报告字段
                                full_report = (graph_state.values.get('final_report') or 
                                             graph_state.values.get('current_report') or 
                                             graph_state.values.get('report'))
                    except Exception as e:
                        st.caption(f"获取完整报告时出错: {str(e)}")
                    
                    # 显示报告内容
                    if full_report:
                        # 使用固定高度的可滚动容器显示完整报告
                        with st.container(height=400, border=True):
                            st.markdown(full_report)
                    elif current_preview:
                        # 如果无法获取完整报告，显示preview片段
                        with st.container(height=200, border=True):
                            st.markdown(current_preview)
                        st.caption("⚠️ 显示的是部分预览，无法获取完整报告内容")
                    else:
                        st.info("无法获取报告预览")
            
            with col_adjustment:
                st.subheader("🔧 章节调整")
                st.markdown("*您可以添加、删除或修改章节*")
                
                # 添加使用说明
                with st.expander("💡 使用说明", expanded=False):
                    st.markdown("""
                    **章节路径格式：**
                    - `1` - 第1章
                    - `2` - 第2章  
                    - `1.2` - 第1章的第2节
                    - `2.1` - 第2章的第1节
                    
                    **操作说明：**
                    - **添加章节：** 在指定位置插入新章节
                    - **删除章节：** 删除指定路径的章节
                    - **修改章节：** 根据您的要求重新生成章节内容
                    
                    **提示：** 每次调整后都会重新生成相关内容，请耐心等待。
                    """)
                
                # 调整操作选择
                adjustment_action = st.selectbox(
                    "选择调整操作:",
                    ["添加章节", "删除章节", "修改章节"],
                    help="选择您要执行的章节调整类型"
                )
                
                st.markdown("---")
                
                if adjustment_action == "添加章节":
                    st.markdown("**添加新章节**")
                    
                    section_path = st.text_input(
                        "插入位置 (章节序号):",
                        placeholder="例如：2 (插入到第2章位置)",
                        help="输入章节序号，新章节将插入到该位置"
                    )
                    
                    section_name = st.text_input(
                        "章节名称:",
                        placeholder="例如：技术实现挑战",
                        help="新章节的标题"
                    )
                    
                    if st.button("➕ 添加章节", type="primary", use_container_width=True):
                        if section_path and section_name:
                            adjustment_data = [{
                                "action": "add",
                                "section_path": section_path,
                                "section_name": section_name
                            }]
                            
                            with st.spinner("正在添加章节并重新生成报告..."):
                                try:
                                    result = safe_asyncio_run(st.session_state.ui.continue_with_section_adjustment(adjustment_data))
                                    
                                    if result["status"] == "completed":
                                        st.session_state.waiting_section_adjustment = False
                                        st.session_state.completed = True
                                        st.session_state.final_report = result["report"]
                                        st.session_state.sections = result.get("sections")
                                        st.success("✅ 章节添加完成！")
                                        st.rerun()
                                    elif result["status"] == "waiting_section_adjustment":
                                        # 可以继续调整
                                        st.session_state.section_adjustment_message = result["interrupt_message"]
                                        st.success("✅ 章节添加完成！您可以继续调整或完成调整。")
                                        st.rerun()
                                    else:
                                        st.error(f"章节调整失败: {result.get('error', '未知错误')}")
                                except Exception as e:
                                    st.error(f"执行过程中出现错误: {str(e)}")
                        else:
                            st.warning("请填写完整的章节信息")
                
                elif adjustment_action == "删除章节":
                    st.markdown("**删除章节**")
                    
                    section_path = st.text_input(
                        "章节路径:",
                        placeholder="例如：1.2 (删除第1章的第2节)",
                        help="输入要删除的章节路径"
                    )
                    
                    if st.button("🗑️ 删除章节", type="secondary", use_container_width=True):
                        if section_path:
                            adjustment_data = [{
                                "action": "delete",
                                "section_path": section_path
                            }]
                            
                            with st.spinner("正在删除章节并重新生成报告..."):
                                try:
                                    result = safe_asyncio_run(st.session_state.ui.continue_with_section_adjustment(adjustment_data))
                                    
                                    if result["status"] == "completed":
                                        st.session_state.waiting_section_adjustment = False
                                        st.session_state.completed = True
                                        st.session_state.final_report = result["report"]
                                        st.session_state.sections = result.get("sections")
                                        st.success("✅ 章节删除完成！")
                                        st.rerun()
                                    elif result["status"] == "waiting_section_adjustment":
                                        # 可以继续调整
                                        st.session_state.section_adjustment_message = result["interrupt_message"]
                                        st.success("✅ 章节删除完成！您可以继续调整或完成调整。")
                                        st.rerun()
                                    else:
                                        st.error(f"章节调整失败: {result.get('error', '未知错误')}")
                                except Exception as e:
                                    st.error(f"执行过程中出现错误: {str(e)}")
                        else:
                            st.warning("请输入要删除的章节路径")
                
                elif adjustment_action == "修改章节":
                    st.markdown("**修改章节**")
                    
                    section_path = st.text_input(
                        "章节路径:",
                        placeholder="例如：2 (修改第2章)",
                        help="输入要修改的章节路径"
                    )
                    
                    modification_prompt = st.text_area(
                        "修改要求:",
                        placeholder="例如：请添加更多技术细节和实际案例",
                        height=100,
                        help="描述您希望如何修改这个章节"
                    )
                    
                    if st.button("✏️ 修改章节", type="primary", use_container_width=True):
                        if section_path and modification_prompt:
                            adjustment_data = [{
                                "action": "modify",
                                "section_path": section_path,
                                "modification_prompt": modification_prompt
                            }]
                            
                            with st.spinner("正在修改章节并重新生成报告..."):
                                try:
                                    result = safe_asyncio_run(st.session_state.ui.continue_with_section_adjustment(adjustment_data))
                                    
                                    if result["status"] == "completed":
                                        st.session_state.waiting_section_adjustment = False
                                        st.session_state.completed = True
                                        st.session_state.final_report = result["report"]
                                        st.session_state.sections = result.get("sections")
                                        st.success("✅ 章节修改完成！")
                                        st.rerun()
                                    elif result["status"] == "waiting_section_adjustment":
                                        # 可以继续调整
                                        st.session_state.section_adjustment_message = result["interrupt_message"]
                                        st.success("✅ 章节修改完成！您可以继续调整或完成调整。")
                                        st.rerun()
                                    else:
                                        st.error(f"章节调整失败: {result.get('error', '未知错误')}")
                                except Exception as e:
                                    st.error(f"执行过程中出现错误: {str(e)}")
                        else:
                            st.warning("请填写完整的修改信息")
                
                st.markdown("---")
                
                # 完成调整按钮
                st.markdown("**完成调整**")
                if st.button("✅ 完成章节调整", type="primary", use_container_width=True):
                    with st.spinner("正在完成最终报告..."):
                        try:
                            # 传递True表示用户确认完成调整
                            result = safe_asyncio_run(st.session_state.ui.continue_with_section_adjustment(True))
                            
                            if result["status"] == "completed":
                                st.session_state.waiting_section_adjustment = False
                                st.session_state.completed = True
                                st.session_state.final_report = result["report"]
                                st.session_state.sections = result.get("sections")
                                st.success("✅ 章节调整完成！")
                                st.rerun()
                            else:
                                st.error(f"完成调整失败: {result.get('error', '未知错误')}")
                        except Exception as e:
                            st.error(f"执行过程中出现错误: {str(e)}")
    
    elif st.session_state.completed and st.session_state.final_report:
        # 步骤4：显示最终报告和styler功能
        st.header("✅ 研究完成")
        
        # 添加进度指示器
        progress_col1, progress_col2, progress_col3, progress_col4 = st.columns(4)
        with progress_col1:
            st.success("✅ 1. 生成计划")
        with progress_col2:
            st.success("✅ 2. 生成报告")
        with progress_col3:
            st.success("✅ 3. 调整章节")
        with progress_col4:
            st.success("✅ 4. 风格转换")
        
        st.markdown("---")

        # 左右两列布局：报告显示和风格控制
        col_report, col_styler = st.columns([2, 1])
        
        with col_report:
            # 1. 风格选择和报告显示
            st.subheader("📝 研究报告")
            
            # 风格选择器
            available_styles = ["原始版本"] + [tag for tag in st.session_state.styled_reports.keys()]
            selected_style = st.selectbox(
                "选择显示版本:",
                available_styles,
                index=available_styles.index(st.session_state.current_style_tag) if st.session_state.current_style_tag in available_styles else 0,
                key="style_selector"
            )
            st.session_state.current_style_tag = selected_style
            
            # 显示选中版本的报告
            if selected_style == "原始版本":
                current_report = st.session_state.final_report
                download_filename = "research_report.md"
            else:
                current_report = st.session_state.styled_reports.get(selected_style, st.session_state.final_report)
                download_filename = f"research_report_{selected_style}.md"
            
            # 报告内容展示
            with st.container(height=600, border=True):
                st.markdown(current_report)
            
            # 下载按钮
            st.download_button(
                label=f"📥 下载 {selected_style} (Markdown)",
                data=current_report,
                file_name=download_filename,
                mime="text/markdown",
                use_container_width=True
            )
        
        with col_styler:
            # 2. 风格转换控制面板
            st.subheader("🎨 风格转换")
            st.markdown("*将原始报告转换为不同的写作风格*")
            
            # 显示当前查看的版本和快速切换
            current_viewing = st.session_state.current_style_tag
            col_status, col_quick = st.columns([2, 1])
            
            with col_status:
                if current_viewing == "原始版本":
                    st.info(f"💡 当前查看：**{current_viewing}**")
                else:
                    st.success(f"💡 当前查看：**{current_viewing}** 风格")
            
            with col_quick:
                # 快速切换到原始版本按钮
                if current_viewing != "原始版本":
                    if st.button("↩️ 原始", help="快速切换到原始版本", use_container_width=True):
                        st.session_state.current_style_tag = "原始版本"
                        st.rerun()
            
            st.markdown("---")
            
            # 获取支持的风格标签并添加中文描述
            supported_tags = get_supported_tags()
            style_descriptions = {
                "tweet": "单一推文风格",
                "tweet-thread": "推文串风格",
                "long-tweet": "长推文风格",
                "generic": "通用风格 - 可自定义的通用转换"
            }
            
            # 创建风格选择选项
            style_options = []
            for tag in supported_tags:
                description = style_descriptions.get(tag, f"{tag}风格")
                style_options.append(f"{tag} - {description}")
            
            # 风格选择
            selected_style_option = st.selectbox(
                "目标风格:",
                style_options,
                help="选择要转换的目标风格"
            )
            
            # 从选择中提取实际的tag
            target_style = selected_style_option.split(" - ")[0] if selected_style_option else ""
            
            # 自定义提示词
            custom_prompt = st.text_area(
                "自定义要求 (可选):",

                height=100,
                placeholder="例如：使用更通俗易懂的语言，增加趣味性...",
                help="您可以添加特殊要求来自定义转换风格"
            )
            
            # 参考文本
            reference_text = st.text_area(
                "参考文本 (可选):",
                height=100,
                placeholder="提供一段您希望模仿的文本风格...",
                help="系统将学习这段文本的风格特征并应用到转换中"
            )
            
            # 转换按钮
            if st.button("🎨 开始风格转换", type="primary", use_container_width=True):
                if target_style:
                    # 检查是否有可转换的报告内容
                    if not st.session_state.final_report:
                        st.error("❌ 没有找到可转换的报告内容。请先完成研究流程生成报告。")
                        return
                    
                    # 检查是否已经转换过这个风格
                    if target_style in st.session_state.styled_reports:
                        st.warning(f"已存在 {target_style} 风格的版本，将覆盖之前的结果")
                    
                    # 获取styler配置，使用用户选择的模型
                    styler_config = {
                        "configurable": {
                            "styler_provider": "openai",
                            "styler_model": st.session_state.get("styler_model", "gpt-4o-mini"),
                            "styler_model_kwargs": {}
                        }
                    }
                    
                    # 显示转换开始
                    st.markdown(f"🎨 **正在转换为 {target_style} 风格...**")
                    
                    try:
                        # 在线程外先获取所需的数据，避免在线程中访问session_state
                        original_text = st.session_state.final_report
                        
                        # 简化的流式显示方法
                        def stream_for_streamlit():
                            """为Streamlit准备的同步生成器"""
                            # 使用线程来运行异步代码
                            import threading
                            import queue
                            
                            result_queue = queue.Queue()
                            exception_queue = queue.Queue()
                            
                            def run_async_stream():
                                try:
                                    async def collect_stream():
                                        async for chunk in convert_text_stream(
                                            original_text=original_text,  # 使用预先获取的数据
                                            tag=target_style,
                                            config=styler_config,
                                            custom_prompt=custom_prompt,
                                            reference_text=reference_text
                                        ):
                                            result_queue.put(chunk)
                                        result_queue.put(None)  # 结束标记
                                    
                                    asyncio.run(collect_stream())
                                except Exception as e:
                                    exception_queue.put(e)
                                    result_queue.put(None)
                            
                            # 启动线程
                            thread = threading.Thread(target=run_async_stream)
                            thread.start()
                            
                            # 从队列中获取结果
                            while True:
                                try:
                                    chunk = result_queue.get(timeout=1.0)
                                    if chunk is None:  # 结束标记
                                        break
                                    yield chunk
                                except queue.Empty:
                                    if not thread.is_alive():
                                        break
                                    continue
                            
                            thread.join()
                            
                            # 检查是否有异常
                            if not exception_queue.empty():
                                raise exception_queue.get()
                        
                        # 使用st.write_stream显示流式内容
                        styled_text = st.write_stream(stream_for_streamlit())
                        
                        if styled_text:
                            # 保存转换结果并切换显示
                            st.session_state.styled_reports[target_style] = styled_text
                            st.session_state.current_style_tag = target_style
                            
                            st.success(f"✅ 已成功转换为 {target_style} 风格！已自动切换显示，您可以使用上方的'↩️ 原始'按钮返回原始版本。")
                            st.rerun()
                        else:
                            st.error("转换失败：未收到任何内容")
                    
                    except Exception as e:
                        st.error(f"风格转换失败: {str(e)}")
                else:
                    st.warning("请选择目标风格")
            
            # 显示已转换的风格列表
            if st.session_state.styled_reports:
                st.markdown("---")
                st.markdown("**已转换的风格:**")
                for style in st.session_state.styled_reports.keys():
                    col_style, col_delete = st.columns([3, 1])
                    with col_style:
                        # 显示当前选中状态
                        button_label = f"📄 {style}"
                        if st.session_state.current_style_tag == style:
                            button_label = f"📄 {style} ✓"
                        
                        if st.button(button_label, key=f"view_{style}"):
                            st.session_state.current_style_tag = style
                            st.rerun()
                    with col_delete:
                        if st.button("🗑️", key=f"delete_{style}", help=f"删除{style}版本"):
                            del st.session_state.styled_reports[style]
                            if st.session_state.current_style_tag == style:
                                st.session_state.current_style_tag = "原始版本"
                            st.rerun()

        st.markdown("---")

        # 3. 显示每个章节的参考文献
        st.subheader("📚 各章节参考文献")

        def display_sources(sections: list, level=0):
            """递归显示章节名称和参考文献"""
            for section in sections:
                # 只显示有参考文献的章节
                if hasattr(section, 'sources') and section.sources:
                    with st.expander(f"章节: {section.name}"):
                        for source in section.sources:
                            st.markdown(f"- {source}")
                
                # 递归处理子章节
                if hasattr(section, 'sections') and section.sections:
                    display_sources(section.sections, level + 1)

        if st.session_state.get("sections"):
            st.info("下方列出了报告中每个章节所引用的参考文献。")
            display_sources(st.session_state.sections)
        else:
            st.warning("无法加载参考文献列表。")
        
        st.markdown("---")

        if st.button("🔄 开始新的研究"):
            # 重置所有状态
            st.session_state.ui.reset_session()
            st.session_state.workflow_started = False
            st.session_state.waiting_feedback = False
            st.session_state.waiting_section_adjustment = False
            st.session_state.completed = False
            st.session_state.final_report = None
            st.session_state.interrupt_message = None
            st.session_state.section_adjustment_message = None
            st.session_state.sections = None
            st.session_state.styled_reports = {}
            st.session_state.current_style_tag = "原始版本"
            st.session_state.show_final_confirmation = False
            st.session_state.workflow_running = False
            st.session_state.workflow_progress = []
            # 重新生成thread_id用于新的研究
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()
    
    # 处理异常状态：completed为True但没有final_report
    elif st.session_state.completed and not st.session_state.final_report:
        st.error("⚠️ 检测到异常状态：研究标记为完成，但没有找到报告内容。")
        st.info("这可能是由于页面刷新或会话中断导致的。请重新开始研究。")
        
        if st.button("🔄 重新开始研究"):
            # 重置所有状态
            st.session_state.ui.reset_session()
            st.session_state.workflow_started = False
            st.session_state.waiting_feedback = False
            st.session_state.waiting_section_adjustment = False
            st.session_state.completed = False
            st.session_state.final_report = None
            st.session_state.interrupt_message = None
            st.session_state.section_adjustment_message = None
            st.session_state.sections = None
            st.session_state.styled_reports = {}
            st.session_state.current_style_tag = "原始版本"
            st.session_state.show_final_confirmation = False
            st.session_state.workflow_running = False
            st.session_state.workflow_progress = []
            # 重新生成thread_id用于新的研究
            st.session_state.thread_id = str(uuid.uuid4())
            st.rerun()

if __name__ == "__main__":
    main() 