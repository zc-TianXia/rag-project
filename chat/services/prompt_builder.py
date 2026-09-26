# chat/services/prompt_builder.py

class RAGPromptBuilder:
    """
    RAG Prompt 构建器
    职责：将检索上下文和用户问题组装为 LLM 可理解的 Prompt
    """

    SYSTEM_TEMPLATE = """你是一个专业的知识库问答助手。请严格根据以下【参考上下文】回答用户问题。
如果上下文中没有相关信息，请明确告知用户你无法回答，不要编造内容。
回答时请引用上下文来源（如：根据文档X...）。

【参考上下文】
{context}
"""

    @classmethod
    def build(cls, query: str, chunks: list[dict]) -> list[dict]:
        """
        Args:
            query: 用户原始问题
            chunks: 检索结果列表，每个元素包含 {'content': str, 'source': str, 'score': float}
        Returns:
            OpenAI 格式的 messages 列表
        """
        if not chunks:
            context_text = "未找到相关参考资料。"
        else:
            # 按相关性排序后拼接，附带来源标记
            sorted_chunks = sorted(chunks, key=lambda x: x.get('score', 0), reverse=True)
            context_parts = []
            for i, chunk in enumerate(sorted_chunks, 1):
                source = chunk.get('source', f'片段{i}')
                context_parts.append(f"[{i}] (来源: {source})\n{chunk['content']}")
            context_text = "\n\n".join(context_parts)

        return [
            {"role": "system", "content": cls.SYSTEM_TEMPLATE.format(context=context_text)},
            {"role": "user", "content": query}
        ]
