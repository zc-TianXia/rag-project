from django.db import models
from pgvector.django import VectorField


class KnowledgeBase(models.Model):
    name = models.CharField(max_length=255, verbose_name="知识库名称")
    description = models.TextField(blank=True, default='', verbose_name="描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "知识库"
        verbose_name_plural = "知识库"

    def __str__(self):
        return self.name


class Document(models.Model):
    file_name = models.CharField(max_length=255, verbose_name="文件名")
    file_path = models.CharField(max_length=500, verbose_name="文件路径")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    # 【新增这一行】建立关联
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.CASCADE,
        verbose_name="所属知识库",
        related_name='documents'  # 方便反向查询，比如 kb.documents.all()
    )

    class Meta:
        db_table = 'rag_document'

    def __str__(self):
        return self.file_name


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, related_name='chunks', on_delete=models.CASCADE, verbose_name="所属文档")
    content = models.TextField(verbose_name="文本内容")
    chunk_index = models.IntegerField(default=0, verbose_name="分块索引")

    # 👇 核心：这就是你装了 pgvector 插件后，Django 存向量的专属字段！
    # text2vec-base-chinese 默认维度是 768
    embedding = VectorField(dimensions=768, null=True, blank=True, verbose_name="向量数据")

    class Meta:
        db_table = 'rag_document_chunk'

    def __str__(self):
        return f"{self.document.file_name} - Chunk {self.chunk_index}"
