# chat/urls.py
from django.urls import path
from . import views

from .views import HealthCheckAPIView
from .views import ChatStreamView

app_name = 'chat'  # 防止命名冲突

urlpatterns = [
    # path('', views.chat_page, name='chat_page'),  这两行是未前后端分离时的程序
    # path('stream/', views.chat_stream, name='chat_stream'),

    path('health/', HealthCheckAPIView.as_view(), name='health-check'),  # 测试地址
    path('stream/', ChatStreamView.as_view(), name='chat-stream'),  # django只认函数，而as_view是个转换器，将类变成函数
]
