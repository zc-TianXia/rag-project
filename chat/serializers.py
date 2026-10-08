# chat/serializers.py
from rest_framework import serializers
import uuid


class ChatRequestSerializer(serializers.Serializer):
    """
    聊天请求参数校验器
    """
    message = serializers.CharField(
        required=True,
        max_length=2000,
        help_text="用户发送的具体问题内容"
    )

    session_id = serializers.CharField(
        required=False,  # 允许不传
        allow_blank=True,
        help_text="会话ID。如果不传，后端会自动生成一个新的会话"
    )

    def validate_session_id(self, value):
        """
        自定义校验逻辑：
        如果前端没传 session_id，或者传的是空字符串，
        我们就自动生成一个 UUID 作为新的会话 ID。
        """
        if not value:
            return str(uuid.uuid4())
        return value

