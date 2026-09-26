# chat/services/llm_service.py
from abc import ABC, abstractmethod
from typing import Generator

class BaseLLMProvider(ABC):
    """LLM 提供者抽象基类"""

    @abstractmethod
    def stream_chat(self, messages: list[dict], **kwargs) -> Generator[str, None, None]:
        """
        流式对话接口
        Yields: 每次产出一个文本片段（token/chunk）
        """
        pass

    @abstractmethod
    def sync_chat(self, messages: list[dict], **kwargs) -> str:
        """非流式对话（用于测试或后台任务）"""
        pass



