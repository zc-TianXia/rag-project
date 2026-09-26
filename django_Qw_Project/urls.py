"""
URL configuration for django_Qw_Project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include # 确保导入了 include


# 1. 导入 drf-spectacular 提供的两个核心视图，swagger的工具
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # 1. 后台管理
    path('admin/', admin.site.urls),

    # 2. 核心 API 路由 (重点修改这里)
    # 含义：所有以 api/chat/ 开头的请求，去掉 api/chat/ 后，转给 chat.urls 处理
    # 对应关系：
    # /api/chat/stream/  --> chat/urls.py 里的 path('stream/', ...)
    # /api/chat/health/  --> chat/urls.py 里的 path('health/', ...)
    path('api/chat/', include('chat.urls')),

    # 3.Swagger 文档路由
    # 这个路径是用来生成 JSON 格式的原始接口数据的（给机器看的）
    # 名字 'schema' 很重要，下面那个视图要靠这个名字找到它
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    # 这个路径就是你等下要在浏览器里访问的可视化网页（给人看的）
    # url_name='schema' 表示去读取上面那个 JSON 数据来渲染页面
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # 4. 如果你还需要以前的首页 HTML 页面，建议单独放这里，不要混在 chat app 里
    # path('', views.index, name='index'),

    # path('api/', include('app01.urls')),    # 未前后端分离前的代码，
    # path('chat/', include('chat.urls')),    # 核心：把根路径 '/' 的所有请求都转给 chat 应用处理

]



