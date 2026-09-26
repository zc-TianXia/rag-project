FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8

WORKDIR /app

# 安装编译工具（不换源，直接用官方默认，配合 host 网络）
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# 单独安装 CPU 版 PyTorch
RUN pip install --no-cache-dir --timeout=120 --retries=5 \
    torch==2.14.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /app/

# 删掉 requirements 里的 torch 行，防止重复装 CUDA 版
RUN sed -i '/^torch[[:space:]]/d' requirements.txt

# 安装其余依赖（走清华 PyPI 源）
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple/

EXPOSE 8000

CMD ["tail", "-f", "/dev/null"]
