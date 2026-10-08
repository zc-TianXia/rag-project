# chat/services/chat_service.py
from .llm_service import BaseLLMProvider
from .openai_provider import OpenAICompatibleProvider
from .prompt_builder import RAGPromptBuilder
import json
from django.conf import settings

from documents.services import RAGIngestionService


# --- 获取 LLM 提供者 ---
def get_llm_provider():
    llm_config = settings.LLM_CONFIG
    return OpenAICompatibleProvider(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        model=llm_config["model"]
    )


# --- 核心流式生成函数 ---
def generate_rag_response_stream(message: str, session_id: str,chunks=None):
    """
    1. 检索：使用新的 RAGIngestionService 从 PostgreSQL 中检索
    2. 生成：使用 LLM 生成流式回答
    """

    # --- 【阶段 1：知识检索 (Retrieval)】 ---
    # 如果外部已经传入了检索结果，就直接用，不再重复检索
    if chunks is None:
        # 没有传，才自己检索（比如直接调用该函数时）
        try:
            rag_service = RAGIngestionService()
            chunks = rag_service.search_knowledge(query_text=message, top_k=3)
            print(f"🔍 检索到 {len(chunks)} 个相关片段")
        except Exception as e:
            print(f"❌ 检索阶段发生错误: {e}")
            chunks = []  # 如果出错，传空列表给 LLM
    else:
        # 外部已有结果，直接打印一下数量方便调试
        print(f"🔍 [检索结果] 共 {len(chunks)} 个片段")


    # --- 【阶段 2：构建 Prompt (Augmentation)】 ---
    # 注意：RAGPromptBuilder 需要的 chunk 格式是 {'content': ..., 'source': ..., 'score': ...}
    # 但services.py 返回的是 {'content': ..., 'source_file': ..., 'score': ...}
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

