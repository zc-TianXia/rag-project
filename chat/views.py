# chat/views.py

import json
from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


# 导入我们之前写好的 Service
from .services.openai_provider import OpenAICompatibleProvider
from .services.prompt_builder import RAGPromptBuilder

# 临时视图
from rest_framework.views import APIView
from rest_framework.response import Response

class HealthCheckAPIView(APIView):
    def get(self, request):
        return Response({"status": "ok", "message": "DRF 环境就绪"})


# 前后端分离时写的代码
from drf_spectacular.utils import extend_schema, OpenApiTypes

# 导入刚才写的序列化器和服务
from .serializers import ChatRequestSerializer
from .services.chat_service import generate_rag_response_stream, get_llm_provider, RAGPromptBuilder

# 导入 RAGIngestionService 以便在这里直接调用检索
from documents.services import RAGIngestionService

class ChatStreamView(APIView):
    # 暂时关闭认证，方便调试
    authentication_classes = []
    permission_classes = []

    @extend_schema(    # swagger的装饰器
        request=ChatRequestSerializer,
        responses={200: OpenApiTypes.OBJECT},
        description="发送问题并获取流式回答 (SSE)"
    )
    def post(self, request):
        # 1. 校验参数
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        user_message = serializer.validated_data['message']
        session_id = serializer.validated_data['session_id']

    # 以下代码是修改代码
        def event_stream():
            # --- 【第一步：获取真实的引用来源数据】 ---
            try:
                # 实例化服务并执行检索（逻辑复用于 chat_service 中的逻辑）
                rag_service = RAGIngestionService()
                chunks = rag_service.hybrid_search(query_text=user_message, top_k=3)

                # 提取真实的文件名 (注意去重)
                # 根据 services.py，字段名是 'source_file'
                real_sources = list({chunk.get('source_file', '未知文件') for chunk in chunks})

                # 构造前端需要的格式
                # 如果前端需要更详细的信息，可以在这里把 chunks 里的 content 也带上
                sources_data = [{"title": name} for name in real_sources]

            except Exception as e:
                print(f"检索引用来源失败: {e}")
                sources_data = [{"title": "检索失败"}]
                chunks = []

            # 发送真实的引用来源
            header_data = {"sources": sources_data}
            yield json.dumps(header_data, ensure_ascii=False) + "\n"

            # --- 【第二步：流式发送 AI 回复正文】 ---
            for chunk in generate_rag_response_stream(user_message, session_id, chunks=chunks):
                yield chunk
            yield "[DONE]"


        # 3. 返回流式响应
        # 注意：content_type 改为 text/plain 或 text/x-quad-stream
        # 因为不再使用标准的 text/event-stream (SSE)
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/plain'  # 改为纯文本流
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

