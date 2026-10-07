# 企业级 RAG 知识库问答系统

基于 Django + Vue3 + pgvector + Redis 的混合检索 RAG 系统，支持向量检索、关键词检索、混合检索三种策略，并集成 DeepSeek 大模型生成回答。


## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Django + Django REST Framework |
| 前端 | Vue3 + Vite |
| 数据库 | PostgreSQL + pgvector |
| 缓存 | Redis |
| 容器 | Docker + docker-compose |
| LLM | DeepSeek + Text2Vec 向量模型 |


## 混合检索原理

系统实现三种检索策略，并支持结果融合：

1. **向量检索**：将查询文本编码为向量，在 pgvector 中按余弦相似度检索 Top-K。
2. **关键词检索**：基于 PostgreSQL 全文检索（tsvector），匹配标题/内容关键词。
3. **混合检索**：取向量检索和关键词检索结果的**并集去重**，再按相关度排序，兼顾语义理解与精确匹配。


## 评测结果

基于 `test_questions.json` 单题评测，计算 Recall@K（命中数 / 期望文档数）：

| 策略 | 平均耗时 | Recall@1 | Recall@3 | 说明 |
|------|---------|----------|----------|------|
| 向量检索 | 880.47ms | 0.333 | N/A | 距离阈值 0.5 过滤后仅返回 1 条 |
| 关键词检索 | 487.29ms | 0.000 | 0.667 | 关键词覆盖不足 |
| 混合检索 | 6.04ms | 0.333 | 0.667 | 并集去重，兼顾两者 |

> N/A 表示因阈值过滤导致返回结果不足 K 条，无法计算。


## 工程优化点

- **Redis 缓存**：向量结果缓存，避免重复计算，混合检索耗时从 880ms 降至 6ms。
- **向量结果复用**：混合检索复用向量检索结果，避免二次查询。
- **单题评测脚本**：支持 `--top-k` 参数，可针对单条问题分析策略差异。


## 快速启动

docker compose up -d  



## 评测命令

docker compose exec web python manage.py evaluate --top-k 5


## 项目结构

django_Qw_Project/

├── chat/               # 聊天应用（LLM 调用、Prompt 构建）

├── documents/          # 文档应用（上传、解析、向量化、检索）

│   └── management/commands/

│       └── evaluate.py # 评测脚本

├── django_qw_project/  # Django 项目配置

└── docker-compose.yml  # 容器编排


## 作者

[zc-TianXia](https://github.com/zc-TianXia)
