# chat/services/chat_service.py
from .llm_service import BaseLLMProvider
from .openai_provider import OpenAICompatibleProvider
from .prompt_builder import RAGPromptBuilder
import json
from django.conf import settings


# --- 1. 导入你的新 Service (核心改动) ---
# 注意：这里假设你的 services.py 在同级目录或 Python 路径下
from documents.services import RAGIngestionService  # 如果报错，可能需要 from documents.services import ...


# --- 获取 LLM 提供者 ---
def get_llm_provider():
    llm_config = settings.LLM_CONFIG
    return OpenAICompatibleProvider(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        model=llm_config["model"]
    )


# --- 核心流式生成函数 ---
def generate_rag_response_stream(message: str, session_id: str):
    """
    1. 检索：使用新的 RAGIngestionService 从 PostgreSQL 中检索
    2. 生成：使用 LLM 生成流式回答
    """

    # --- 【阶段 1：知识检索 (Retrieval)】 ---
    try:
        # 实例化你的服务
        rag_service = RAGIngestionService()

        # 调用检索方法 (这里的逻辑完全基于你发给我的 services.py)
        # 注意：search_knowledge 是你代码里写的方法名
        chunks = rag_service.search_knowledge(query_text=message, top_k=3)

        print(f"🔍 检索到 {len(chunks)} 个相关片段")  # 打印日志，方便你调试

    except Exception as e:
        print(f"❌ 检索阶段发生错误: {e}")
        chunks = []  # 如果出错，传空列表给 LLM

    # --- 【阶段 2：构建 Prompt (Augmentation)】 ---
    # 注意：RAGPromptBuilder 需要的 chunk 格式是 {'content': ..., 'source': ..., 'score': ...}
    # 但你的 services.py 返回的是 {'content': ..., 'source_file': ..., 'score': ...}
    # 所以需要做一个简单的转换
    formatted_chunks = []
    for chunk in chunks:
        formatted_chunks.append({
            'content': chunk['content'],
            'source': chunk['source_file'],  # 字段名映射
            'score': chunk['score']
        })

    # 调用 PromptBuilder 组装消息
    messages = RAGPromptBuilder.build(message, formatted_chunks)

    # --- 【阶段 3：LLM 生成 (Generation)】 ---
    provider = get_llm_provider()

    try:
        # 流式返回 AI 的回答
        for chunk in provider.stream_chat(messages):
            yield chunk
    except Exception as e:
        yield f"\n\n[AI 生成错误: {str(e)}]"

