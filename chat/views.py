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
                # 根据你的 services.py，字段名是 'source_file'
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
            # 这里继续调用原来的生成器获取回答内容
            for chunk in generate_rag_response_stream(user_message, session_id, chunks=chunks):
                yield chunk
            yield "[DONE]"


        # # 2. 定义事件流生成器 (核心修改点)
        # def event_stream():
        #     # --- 【第一步：准备引用来源数据】 ---
        #     # 注意：这里的数据结构要和前端约定好
        #     # 假设你从 service 里能拿到 sources 列表
        #     # 为了演示，我先用 mock 数据，你后面要替换成真实的检索结果
        #     mock_sources = [
        #         {"title": "测试文档.pdf", "content": "这是从数据库检索到的片段...", "score": 0.95}
        #     ]
        #
        #     # 【关键】：构造一个只包含 sources 的字典，并转成 JSON 字符串
        #     # 注意：这里不能有多余的空格或换行，必须是合法 JSON
        #     header_data = {"sources": mock_sources}
        #     header_json = json.dumps(header_data, ensure_ascii=False)
        #
        #     # 【关键】：发送第一行 (JSON Header)
        #     # 前端会读取第一行来解析引用来源
        #     yield header_json + "\n"  # 必须以 \n 结尾，作为行结束标志
        #
        #     # --- 【第二步：流式发送 AI 回复正文】 ---
        #     # 调用 Service 层获取生成器
        #     # 注意：generate_rag_response_stream 是你 chat_service.py 里的函数
        #     for chunk in generate_rag_response_stream(user_message, session_id):
        #         # 直接发送文本块，不需要包装成 SSE 格式 (即不需要 "data: "前缀)
        #         # 前端会把除了第一行以外的所有内容都视为 Markdown 正文
        #         yield chunk
        #
        #     # --- 【第三步：发送结束标志 (可选)】 ---
        #     # 虽然流结束就是结束，但为了保险，可以发一个结束符
        #     # 前端如果检测到 [DONE] 可以做一些收尾工作
        #     yield "[DONE]"

        # 3. 返回流式响应
        # 注意：content_type 改为 text/plain 或 text/x-quad-stream
        # 因为我们不再使用标准的 text/event-stream (SSE)
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/plain'  # 改为纯文本流
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

# 以下代码是我之前用templates里面index做项目测试的代码。
# 导入你的文档模型（根据你 documents 应用里的实际导入路径调整）
# from documents.services import RAGIngestionService
#
# def chat_page(request):
#     """渲染前端聊天页面"""
#     return render(request, 'chat/index.html')
#
#
# @csrf_exempt  # 为了方便测试，暂时免除 CSRF 校验（生产环境建议通过 header 传 token）
# def chat_stream(request):
#     """处理用户的提问，并返回 SSE 流式响应"""
#     if request.method != "POST":
#         return JsonResponse({"error": "Only POST allowed"}, status=405)
#
#     try:
#         body = json.loads(request.body)
#         query = body.get("query", "").strip()
#         if not query:
#             return JsonResponse({"error": "Query is empty"}, status=400)
#     except json.JSONDecodeError:
#         return JsonResponse({"error": "Invalid JSON"}, status=400)
#
#     # 实例化你的 Service
#     rag_service = RAGIngestionService()
#
#     # 使用生成器函数来处理流式逻辑
#     response = StreamingHttpResponse(
#         generate_rag_response(query,rag_service),
#         content_type="text/event-stream"  # 关键：告诉浏览器这是一个 SSE 流
#     )
#     # 禁用缓存，确保流式数据实时到达
#     response["Cache-Control"] = "no-cache"
#     response["X-Accel-Buffering"] = "no"  # 如果你用了 Nginx，这行能防止 Nginx 缓冲流数据
#     return response


# def generate_rag_response(query: str, rag_service: RAGIngestionService):
#     """
#     核心 RAG 逻辑：检索 -> 组装 Prompt -> LLM 生成 -> 格式化 SSE 数据
#     """
#     # ==========================================
#     # 第一步：知识检索 (Retrieval) - 直接调用你的函数
#     # ==========================================
#     try:
#         # 直接调用你原来的函数逻辑
#         chunks = rag_service.search_knowledge(query, top_k=3)
#
#         if not chunks:
#             chunks = [{"content": "抱歉，知识库中未找到相关信息。", "source_file": "System", "score": 1.0}]
#
#     except Exception as e:
#         print(f"检索出错: {e}")
#         chunks = [{"content": "检索服务暂时不可用。", "source_file": "System", "score": 1.0}]
#     # ==========================================
#     # 第二步：构建 Prompt (Augmentation)
#     # ==========================================
#     messages = RAGPromptBuilder.build(query, chunks)
#
#     # ==========================================
#     # 第三步：调用 LLM 并流式返回 (Generation)
#     # ==========================================
#     llm_config = settings.LLM_CONFIG
#     provider = OpenAICompatibleProvider(
#         api_key=llm_config["api_key"],
#         base_url=llm_config["base_url"],
#         model=llm_config["model"]
#     )
#
#     # --- 【新增逻辑：提取引用来源】 ---
#     # 从检索结果 chunks 中提取 source_file
#     # 使用 set 去重，防止同一个文档出现多次
#     source_files = list({chunk.get('source_file', '未知文件') for chunk in chunks})
#
#     # --- 【修改点】：流式输出文字 ---
#     # 调用底层 Service 的流式接口
#     for token in provider.stream_chat(messages):
#         # 修改 JSON 结构，加上 type 字段
#         payload = json.dumps({
#             "type": "text",
#             "content": token
#         })
#         yield f"data: {payload}\n\n"
#
#     # --- 【新增逻辑：发送引用来源】 ---
#     # 在文字输出完毕后，发送引用信息
#     # 前端会根据 type: reference 来渲染卡片
#     payload = json.dumps({
#         "type": "reference",
#         "sources": source_files
#     })
#     yield f"data: {payload}\n\n"
#
#     # 发送结束标志
#     yield "data: [DONE]\n\n"
