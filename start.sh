#!/bin/bash
echo "等待数据库启动..."
python -c '
import socket, time
while True:
    try:
        socket.create_connection(("db", 5432), 2)
        break
    except:
        print("数据库还没好，等2秒...")
        time.sleep(2)
'
echo "数据库已就绪，开始执行数据库迁移..."
python manage.py migrate

echo "启动 Django 开发服务器..."
python manage.py runserver 0.0.0.0:8000
