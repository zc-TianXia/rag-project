from django.contrib import admin
# 从当前应用的 models 导入这两个类
from .models import ChatSession, ChatMessage

# 注册这两个模型
admin.site.register(ChatSession)
admin.site.register(ChatMessage)