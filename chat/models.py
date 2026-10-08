# chat/models.py
import uuid
from django.db import models
from django.conf import settings


class ChatSession(models.Model):
    """对话会话，承载多轮对话上下文"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_base = models.ForeignKey(
        'documents.KnowledgeBase',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions',
        verbose_name="关联知识库"
    )
    title = models.CharField(max_length=255, default="新对话", verbose_name="会话标题")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rag_chat_session'
        verbose_name = "对话会话"
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class ChatMessage(models.Model):
    """单条消息记录"""

    class Role(models.TextChoices):
        USER = 'user', '用户'
        ASSISTANT = 'assistant', 'AI助手'
        SYSTEM = 'system', '系统'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')

    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField(verbose_name="消息内容")

    # 亮点：记录 AI 回答时引用的 chunks，支持前端展示"参考来源"
    referenced_chunks = models.ManyToManyField(
        'documents.DocumentChunk',
        blank=True,
        related_name='referenced_in_messages',
        verbose_name="引用的知识切片"
    )

    # 记录该消息使用的 token 数（可选，用于成本统计）
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rag_chat_message'
        verbose_name = "对话消息"
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}..."
