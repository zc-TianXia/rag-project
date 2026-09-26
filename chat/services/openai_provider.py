# chat/services/openai_provider.py

import json
import requests
from typing import Generator
from django.conf import settings
from .llm_service import BaseLLMProvider


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    兼容 OpenAI 格式的 LLM 提供者（完美适配硅基流动、DeepSeek、通义千问等）。
    使用轻量级的 requests 库实现流式响应解析。
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        # 确保 base_url 结尾没有斜杠，并拼上 /v1/chat/completions
        self.base_url = base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/v1/chat/completions"
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def stream_chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 2048) -> Generator[
        str, None, None]:
        """
        流式对话接口。
        Yields: 每次产出一个文本片段（token）。
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,  # 开启流式
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            # 使用 requests 的 stream=True 开启流式请求
            with requests.post(self.endpoint, json=payload, headers=self.headers, stream=True, timeout=60) as response:
                response.raise_for_status()  # 检查 HTTP 状态码

                # iter_lines() 会自动按行读取流数据，非常适合处理 SSE
                for line in response.iter_lines():
                    if not line:
                        continue

                    # 将字节流解码为字符串
                    decoded_line = line.decode('utf-8')

                    # SSE 格式的数据通常以 "data: " 开头
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:].strip()

                        # 硅基流动/OpenAI 流结束的标志
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            # 提取流式返回的增量内容 (delta)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield content  # 将内容逐块返回给调用者

                        except (json.JSONDecodeError, KeyError, IndexError):
                            # 忽略解析错误的脏数据，继续读取下一行
                            continue

        except requests.exceptions.RequestException as e:
            # 如果请求失败（如网络问题、API Key 错误），抛出一个友好的错误信息给前端
            yield f"\n\n[Error: 连接大模型失败 - {str(e)}]"

    def sync_chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        非流式对话（用于后台测试或不支持流式的场景）。
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(self.endpoint, json=payload, headers=self.headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

