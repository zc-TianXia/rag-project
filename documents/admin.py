from django.contrib import admin
# 从当前应用的 models 导入这三个类
from .models import Document, DocumentChunk, KnowledgeBase

# 注册这三个模型，这样后台才会显示
admin.site.register(Document)
admin.site.register(DocumentChunk)
admin.site.register(KnowledgeBase)
