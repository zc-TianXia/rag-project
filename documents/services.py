import os
from pathlib import Path
from django.conf import settings
from .models import Document, DocumentChunk,KnowledgeBase
from pgvector.django import CosineDistance
from django.db.models import F
from django.core.cache import cache
import hashlib
import time
import jieba
from django.db.models import Q

# 强制断网环境变量
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


class RAGIngestionService:
    _instance = None # 类属性，用来存唯一实例

    def __new__(cls):
        # 重写 __new__ 方法：控制创建实例的过程
        if cls._instance is None:
            print("🔄 第一次创建实例，加载模型...")
            cls._instance = super().__new__(cls)
        else:
            print("✅ 复用已有实例，不加载模型")
        return cls._instance

    def __init__(self):
        # 防止重复初始化属性
        if not hasattr(self, '_initialized'):
            print("正在初始化 RAG 服务（纯本地 Django + PGVector 模式）...")
            try:
                from text2vec import SentenceModel
                # 直接加载本地模型
                self.embedding_model = SentenceModel('shibing624/text2vec-base-chinese')
                print("✅ Embedding 模型加载成功！")
            except Exception as e:
                print(f"❌ 模型加载失败: {e}")
                raise e
            self._initialized = True


    # 万物皆对象，list等数据类型只不过python底层封装了类，所以可以直接用语法糖，如a=[],
    # 像path类由于太大，所以需要导入才能实例化，其他的时候想创建对象只能用自己创建的类实例化
    def _load_file(self, file_path: Path) -> str:
        """纯原生读取文件，绝不联网"""
        suffix = file_path.suffix.lower()
        if suffix == '.txt':
            for enc in ['utf-8', 'gbk']:   #  大部分都是utf-8的编码，少部分是gbk中文编码
                try:
                    return file_path.read_text(encoding=enc)
                except UnicodeDecodeError:
                    continue
        elif suffix == '.pdf':
            import fitz
            doc = fitz.open(file_path)  # doc是document对象，这个对象类型本身可以遍历
            text = "\n".join([page.get_text("text") for page in doc])  #  page是每一页的对象
            doc.close()
            return text
        elif suffix == '.docx':
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])  # p是paragraph对象，doc.paragraphs则是列表
        return ""

    def _chunk_text(self, text: str, chunk_size=500, overlap=50):
        """滑动窗口切分文本"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size  #  [0、500], [450、950],[900、1400],[1350、1850]
            chunks.append(text[start:end])   # [start:end] 底层是魔法函数，跟加减号类似。
            if end >= len(text):
                break
            start += (chunk_size - overlap)
        return chunks

    def process_folder(self, folder_path=None):
        """
        处理文件夹中的文档：读取 -> 切分 -> 向量化 -> 入库 (完整闭环)
        """
        # 1. 确定路径
        if folder_path is None:
            target_dir = settings.KNOWLEDGE_BASE_DIR
        else:
            target_dir = folder_path
        target_path = Path(target_dir)

        if not target_path.exists():
            print(f" 错误：路径不存在 -> {target_dir}")
            return

        print(f"🚀 开始处理文件夹: {target_dir}")

        # 2. 获取或创建 KnowledgeBase 对象
        kb_name = target_path.name
        kb_obj, created = KnowledgeBase.objects.get_or_create(   # get_or_create返回的是元组
            name=kb_name,
            defaults={'description': f'自动导入的知识库: {kb_name}'}
        )
        if created:
            print(f"✅ 成功创建知识库: '{kb_name}' (ID: {kb_obj.id})")
        else:
            print(f"ℹ️ 使用现有知识库: '{kb_name}' (ID: {kb_obj.id})")

        # 3. 遍历文件并处理
        file_count = 0
        for file_path in target_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.txt', '.pdf', '.docx', '.md']:
                try:
                    # --- 步骤 A: 检查文件是否已存在 ---
                    doc_obj, created = Document.objects.get_or_create(
                        file_name=file_path.name,
                        knowledge_base=kb_obj,  # 确保关联
                        defaults={'file_path': str(file_path)}
                    )

                    if not created:
                        print(f" ⚠️ 跳过 (已存在): {file_path.name}")
                        continue

                    print(f"📄 正在处理新文件: {file_path.name}")

                    # --- 步骤 B: 读取文本 ---
                    text = self._load_file(file_path)
                    if not text.strip():
                        print(f" 空文件跳过: {file_path.name}")
                        continue

                    # --- 步骤 C: 文本切分 ---
                    chunks = self._chunk_text(text, chunk_size=500, overlap=50)
                    print(f"✂️ 切分完成，共得到 {len(chunks)} 个片段")

                    # --- 步骤 D: 向量化并存入 PGVector (核心步骤) ---
                    chunk_objects = []
                    for i, chunk_content in enumerate(chunks):
                        # 生成向量
                        embedding_vector = self.embedding_model.encode(chunk_content).tolist()

                        # 创建 DocumentChunk 对象 (注意：embedding 字段对应 PGVector 的 VectorField)
                        chunk_obj = DocumentChunk(
                            document=doc_obj,
                            content=chunk_content,
                            chunk_index=i,
                            embedding=embedding_vector  # 直接存入向量列表
                        )
                        chunk_objects.append(chunk_obj)

                    # 数据库批量插入，提高效率
                    if chunk_objects:
                        DocumentChunk.objects.bulk_create(chunk_objects)
                        print(f"✅ 成功入库 {len(chunk_objects)} 个向量片段")

                    file_count += 1

                except Exception as e:
                    print(f"❌ 处理文件失败 {file_path.name}: {e}")

        print(f"🎉 处理完成！共处理 {file_count} 个新文件，知识库构建完毕。")

    def search_knowledge(self, query_text: str, top_k: int = 3, use_cache: bool = True):
        """
        纯本地检索逻辑：根据用户问题查找最相关的知识库片段
        :param query_text: 用户的问题
        :param top_k: 返回最相关的前 N 个片段
        :return: 包含相关文本片段的列表
        """
        print(f"🔍 [本地检索] 正在分析查询: '{query_text}'")

        # ========== Redis 缓存部分（新增） ==========
        # 用查询文本生成唯一的缓存 key（避免特殊字符问题）
        start_time = time.perf_counter()  # 开始计时
        cache_key = "rag_search_" + hashlib.md5(query_text.encode()).hexdigest()
        if use_cache:  # <--- 加个开关
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                print(f"⚡️ [缓存命中] 直接返回缓存结果，跳过检索")
                return cached_result
        # ========== Redis 缓存部分结束 ==========


        # 1. 将用户的问题转化为向量 (使用本地加载的 embedding 模型)
        query_vector = self.embedding_model.encode([query_text])[0].tolist()

        # 2. 先排序，取前 top_k 个（不要急着 filter！）
        raw_results = (
            DocumentChunk.objects
            .annotate(distance=CosineDistance('embedding', query_vector))
            .order_by('distance')[:top_k]
        )

        # 3. 手动遍历，加阈值判断
        relevant_chunks = []
        for chunk in raw_results:
            # 只有当距离小于阈值时，才收录
            if chunk.distance < 0.5:
                relevant_chunks.append({
                    'id':chunk.id,
                    'content': chunk.content,
                    'source_file': chunk.document.file_name,
                    'score': chunk.distance
                })
                print(f"✅ 收录相关片段 (距离: {chunk.distance:.4f})")
            else:
                print(f"❌ 跳过不相关片段 (距离: {chunk.distance:.4f} >= 0.5)")

        # 4. 如果一个都没收录，提示用户
        if not relevant_chunks:
            print("⚠️ 未找到足够相关的知识库内容（可能需要调整阈值）。")


        # ========== Redis 缓存部分（新增） ==========
        # 将本次检索结果存入 Redis，有效期 1 小时（3600 秒）
        if use_cache:  # <--- 加个开关
            cache.set(cache_key, relevant_chunks, 3600)
            print(f"💾 [缓存存储] 结果已缓存，1小时内相同问题直接返回")
        end_time = time.perf_counter()
        print(f"💾 [正常检索并缓存] 总耗时: {end_time - start_time:.4f}秒")
        # ========== Redis 缓存部分结束 ==========

        return relevant_chunks


    def keyword_search(self, query_text, top_k=5):
        # 1. 分词：用 jieba 拆前端提问
        words = jieba.lcut(query_text)
        words = [w for w in words if len(w.strip()) > 1]  # 过滤单字噪音
        if not words:
            return []

        # 2. 构造 ORM 动态 OR 查询（自动防 SQL 注入，自动用 rag_document_chunk 表）
        q = Q()
        for w in words:
            q |= Q(content__icontains=w)  # 等价于 content LIKE '%词%'

        # 3. 查询：select_related 提前 JOIN document 拿文件名，避免额外查询
        rows = DocumentChunk.objects.filter(q).select_related('document')[:top_k]

        # 4. 格式化返回：必须包含 id（供混合检索融合），source_file 从外键拿
        chunks = []
        for chunk in rows:
            chunks.append({
                'id': chunk.id,  # ← 关键：混合检索要去重，必须有 id
                'content': chunk.content,
                'source_file': chunk.document.file_name,  # 外键拿文件名，不是直接列
                'chunk_index': chunk.chunk_index,
                'score': 1.0  # 关键词命中给个默认分
            })
        return chunks

    def hybrid_search(self, query_text, top_k=5, vector_chunks=None):
        # 1. 混合检索自己的独立缓存 Key（加上了 hybrid 前缀和 top_k）
        cache_key = "rag_hybrid_search_" + str(top_k) + "_" + hashlib.md5(query_text.encode()).hexdigest()

        # 2. 先看看自己的抽屉里有没有
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            print(f"⚡️ [混合检索缓存命中] 直接返回融合结果，跳过双重检索")
            return cached_result

        # 3. 如果没有缓存，开始干活...
        print(f"🔍 [混合检索] 开始向量+关键词双重检索...")

        """
        混合检索：向量检索 + 关键词检索，然后用 RRF 融合排序。
        """
        # 1. 向量检索（你原来的方法）
        if vector_chunks is None:
            vector_chunks = self.search_knowledge(
                query_text, top_k=top_k, use_cache=False
            )

        # 2. 关键词检索（我们刚写的）
        keyword_chunks = self.keyword_search(query_text, top_k=top_k)

        # 3. RRF 融合
        # RRF 公式：score = 1 / (60 + rank)
        # rank 是片段在某个结果列表中的排名（从0开始）
        rrf_score = {}

        for rank, chunk in enumerate(vector_chunks):
            chunk_id = chunk['id']
            rrf_score[chunk_id] = rrf_score.get(chunk_id, 0) + 1 / (60 + rank)

        for rank, chunk in enumerate(keyword_chunks):
            chunk_id = chunk['id']
            rrf_score[chunk_id] = rrf_score.get(chunk_id, 0) + 1 / (60 + rank)

        # 4. 合并片段信息，并按融合后的分数排序
        combined = {}
        all_chunks = vector_chunks + keyword_chunks
        for chunk in all_chunks:
            combined[chunk['id']] = chunk

        # 给每个片段补上融合后的分数
        for chunk_id, score in rrf_score.items():
            if chunk_id in combined:
                combined[chunk_id]['rrf_score'] = score

        # 按 rrf_score 从大到小排序
        sorted_chunks = sorted(combined.values(), key=lambda x: x.get('rrf_score', 0), reverse=True)

        # 返回前 top_k 个
        return sorted_chunks[:top_k]





