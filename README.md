# 📚 JustWord - 后端 API

> JustWord 学习应用的后端 API 服务，基于 FastAPI + MySQL 构建。

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql)](https://mysql.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 功能特性

- 📝 单词 CRUD 操作
- 🔐 JWT 用户认证
- 🧠 AI 翻译智能判断 (DeepSeek)
- 📊 学习记录追踪
- 🐳 Docker 容器化部署

---

## 🛠️ 技术栈

| 技术 | 说明 |
|------|------|
| **FastAPI** | Web 框架 |
| **SQLAlchemy** | ORM |
| **MySQL** | 数据库 |
| **JWT** | 用户认证 |
| **DeepSeek API** | AI 翻译判断 |

---

## 🚀 快速开始

### 前置要求

- Python 3.11+
- MySQL 8.0+
- Docker (可选)

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/XuLin8/JustWord-backend.git
cd JustWord-backend

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入数据库配置

# 5. 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

### Docker 运行

```bash
# 1. 克隆仓库
git clone https://github.com/XuLin8/JustWord-backend.git
cd JustWord-backend

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入数据库配置

# 3. 启动所有服务（后端 + MySQL）
docker-compose up -d

# 4. 查看日志
docker-compose logs -f

# 5. 停止服务
docker-compose down
```

---

## 📡 API 文档

启动后访问：

- Swagger UI: `http://localhost:3000/docs`
- ReDoc: `http://localhost:3000/redoc`

---

## 📁 项目结构

```
justword-backend/
├── app/
│   ├── routers/      # API 路由
│   ├── models.py     # 数据库模型
│   ├── schemas.py    # Pydantic 模型
│   ├── database.py   # 数据库连接
│   └── main.py       # 应用入口
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🔗 相关链接

- [前端仓库](https://github.com/XuLin8/JustWord-frontend)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

---

## 📄 许可证

无

---

⭐ 如果这个项目对你有帮助，请给个 Star！
