import os
from pathlib import Path
from django.conf import settings
from .models import Document, DocumentChunk,KnowledgeBase
from pgvector.django import CosineDistance
from django.db.models import F


# 强制断网环境变量
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


class RAGIngestionService:
    def __init__(self):
        print("🚀 正在初始化 RAG 服务 (纯本地 Django + PGVector 模式)...")
        try:
            from text2vec import SentenceModel
            # 直接加载本地模型
            self.embedding_model = SentenceModel('shibing624/text2vec-base-chinese')
            print("✅ Embedding 模型加载成功！")
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            raise e


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


    def search_knowledge(self, query_text: str, top_k: int = 3):
        """
        纯本地检索逻辑：根据用户问题查找最相关的知识库片段
        :param query_text: 用户的问题
        :param top_k: 返回最相关的前 N 个片段
        :return: 包含相关文本片段的列表
        """
        print(f"🔍 [本地检索] 正在分析查询: '{query_text}'")

        # 1. 将用户的问题转化为向量 (使用本地加载的 embedd ing 模型)
        # 注意：这里复用了你之前实例化时加载的 self.embedding_model
        query_vector = self.embedding_model.encode([query_text])[0].tolist()

        # ... (前面的代码不变) ...

        # 1. 先排序，取前 top_k 个（不要急着 filter！）
        raw_results = (
            DocumentChunk.objects
                .annotate(distance=CosineDistance('embedding', query_vector))
                .order_by('distance')[:top_k]  # 先拿前3个看看
        )

        # 2. 手动遍历，加阈值判断
        relevant_chunks = []
        for chunk in raw_results:
            # 只有当距离小于阈值时，才收录
            if chunk.distance < 0.5:
                relevant_chunks.append({
                    'content': chunk.content,
                    'source_file': chunk.document.file_name,
                    'score': chunk.distance
                })
                print(f"✅ 收录相关片段 (距离: {chunk.distance:.4f})")
            else:
                print(f"❌ 跳过不相关片段 (距离: {chunk.distance:.4f} >= 0.5)")

        # 3. 如果一个都没收录，提示用户
        if not relevant_chunks:
            print("⚠️ 未找到足够相关的知识库内容（可能需要调整阈值）。")

        return relevant_chunks

    def search(self, query, k=3):
        """
        向量检索优化版
        """
        print(f"🔍 正在搜索: {query}")
        query_vec = self.model.encode(query).tolist()

        # 使用 PGVector 的专用检索语法 (比 annotate 更快)
        # 注意：CosineDistance 在这里表示 "距离越小越相似"
        results = DocumentChunk.objects.filter(
            embedding=CosineDistance(query_vec)  # 修正了原代码中的写法
        ).order_by('distance')[:k]

        # 输出结果
        for i, res in enumerate(results):
            print(f"👉 {i + 1}. [{res.document.file_name}] (距离: {res.distance:.4f})")
            print(f"   内容: {res.content[:60]}...\n")

        return results
