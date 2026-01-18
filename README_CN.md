<div align="center">
  <img src="img/logo.png" alt="EyeOfWeb Logo" width="300" onError="this.style.display='none'"/>

  # 👁️ EyeOfWeb

  ### 先进的基于Web的面部情报与安全分析平台
  ### Advanced Web-Based Facial Intelligence & Security Analysis Platform

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  ![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
  ![Framework](https://img.shields.io/badge/flask-2.0+-green.svg)
  ![Database](https://img.shields.io/badge/PostgreSQL-13+-336791.svg)
  ![Vector DB](https://img.shields.io/badge/Milvus-2.3+-00a1ea.svg)
  ![AI Model](https://img.shields.io/badge/InsightFace-AntelopeV2-orange.svg)
  ![Status](https://img.shields.io/badge/Status-Active%20Development-green)

  ---

  **[🇹🇷 Türkçe Dokümantasyon](README.md#-türkçe-dokümantasyon)** | **[🇬🇧 English Documentation](README.md#-english-documentation)** | **[🇷🇺 Russian Documentation](README_RU.md)** | **[🇨🇳 Chinese Documentation](#-chinese-documentation)**

</div>

---

> [!IMPORTANT]
> ## 📜 法律免责声明 / LEGAL DISCLAIMER
>
> ### 🇨🇳 中文
> **EyeOfWeb** 严格用于学术研究、教育和法律安全模拟。未经同意对真实个人使用本软件，未经授权收集或存储个人数据，可能违反土耳其数据保护法 (**KVKK**)、欧盟通用数据保护条例 (**GDPR**) 和其他国际隐私法律，并可能导致严重的法律制裁。
>
> 项目开发者对软件的任何非法或不道德使用不承担任何直接或间接的法律、财务或刑事责任。**最终用户承担全部法律和道德责任。**
>
> ### 🇬🇧 English
> **EyeOfWeb** has been developed strictly for academic research, education, and legal security simulations. Unauthorized use, collection, or storage of personal data on real individuals may violate **KVKK** (Turkish Data Protection Law), **GDPR**, and other international privacy laws, resulting in serious legal penalties.
>
> The developers assume no direct or indirect legal, financial, or criminal liability for any illegal or unethical use of the software. **The end-user bears full legal and ethical responsibility.**

---

## 🇨🇳 Chinese Documentation

---

### 📋 目录 (Table of Contents)

1.  [🐳 Docker 快速入门](#-docker-快速入门--quick-start-with-docker)
2.  [执行摘要](#-执行摘要--executive-summary)
3.  [核心功能与能力](#-核心功能与能力)
4.  [技术架构](#-技术架构)
5.  [技术栈](#-技术栈-tech-stack)
6.  [项目结构](#-项目结构)
7.  [安装指南](#️-安装指南)
8.  [配置选项](#️-配置选项)
9.  [许可证](#-许可证)
10. [致谢与贡献者](#-致谢与贡献者)
11. [用户界面截图](#-用户界面截图)

---

### 📚 详细文档 / Detailed Documentation

| 文件 / File | 描述 / Description |
|--------------|------------------------|
| [doc/DOCKER.md](doc/DOCKER.md) | 🐳 Docker 安装与管理指南 |
| [doc/CRAWLER.md](doc/CRAWLER.md) | 🕷️ 爬虫用户指南 (土耳其语) |
| [doc/CRAWLER_EN.md](doc/CRAWLER_EN.md) | 🕷️ Crawler user guide (English) |
| [doc/CHANGELOG.md](doc/CHANGELOG.md) | 📝 变更日志 / Changelog |

---

### 🐳 Docker 快速入门 / Quick Start with Docker

> [!TIP]
> **最快的入门方法是使用 Docker！**
> **Docker is the fastest way to get started!**
>
> **注意 / Note:** Docker 镜像默认使用 **Torch CPU** 版本以节省空间。如果需要使用 GPU，您可能需要修改 `src/Dockerfile` 中的 Torch 安装配置。
> **Note:** The Docker image uses the **Torch CPU** version by default to save space. You may need to modify the Torch installation in `src/Dockerfile` for GPU usage.

```bash
# 1. 克隆仓库
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web/src

# 2. 使用 Docker Compose 启动
sudo docker compose up -d --build

# 3. 查看日志
sudo docker compose logs -f web
```

**访问地址:** http://localhost:5000
**默认管理员:** `admin` / `admin123_changeme`

#### 服务 / Services

| 服务 / Service | 端口 | 描述 / Description |
|------------------|------|------------------------|
| Web 应用 | 5000 | 主 Web 界面 / Main web interface |
| PostgreSQL | 5432 | 关系型数据库 / Relational database |
| Milvus | 19530 | 向量数据库 / Vector database |
| Crawler Worker | - | 后台爬虫 / Background crawler |

> 📖 **详细安装说明:** [doc/DOCKER.md](doc/DOCKER.md)

---

### 🎥 示例用法与分析视频 (Example Usage & Analysis Videos)

#### 1. 一般使用示例 (General Usage Example)
[![EyeOfWeb Usage Example](https://img.youtube.com/vi/s_Ak0tiq1f4/0.jpg)](https://www.youtube.com/watch?v=s_Ak0tiq1f4)

#### 2. 综合人员分析 (Comprehensive Person Analysis)
[![EyeOfWeb Comprehensive Analysis](https://img.youtube.com/vi/gdoNdIjJr5E/0.jpg)](https://www.youtube.com/watch?v=gdoNdIjJr5E)

---

### 📄 执行摘要 / Executive Summary

**EyeOfWeb** 是一个综合性的专业安全情报平台，结合了开源情报 (OSINT) 方法论与基于深度学习的下一代生物特征分析技术。

系统自主抓取互联网上各种来源（新闻门户、博客、RSS 源等）的视觉数据，检测这些图像中的面部，为每个人脸创建一个独特的数学向量（embedding），并将这些向量索引到高性能向量数据库 (Milvus) 中。同时，检测到的人脸的来源、日期和风险等级等元数据存储在关系型数据库 (PostgreSQL) 中。

凭借这种“混合数据库架构”，EyeOfWeb 可以在**毫秒级**时间内在数十亿人脸数据中执行高级分析，如 1:N 身份搜索、1:1 人脸比对、社会关系网络/关联分析和人员画像。

---

### 🚀 核心功能与能力

以下详细说明了在 `src/app/routes/web.py` 模块中定义并可通过用户界面/API 访问的所有核心功能。

---

#### 1. 综合人员分析 (Comprehensive Person Analysis)

这是 EyeOfWeb 最强大和复杂的分析工具。它基于特定人员的照片执行全面的社会计量分析。

**路由:** `/comprehensive_person_analysis/<face_id>`

**工作原理:**
1.  **目标与上下文收集:** 收集目标人脸 (`face_id`) 以及出现在同一画面中的所有其他人脸。
2.  **全聚类 (Cluster All) 策略:** 使用先进的贪婪聚类算法将所有收集到的人脸（包括目标）聚类在一起。这可以完美地将目标人物与长相相似的人（如替身）或错误检测区分开来。
3.  **目标簇识别:** 使用原始人脸数据和向量相似度识别属于“目标人物”的簇。
4.  **关系分析:** 仅统计“目标簇”中的人脸与“不同簇”中的人脸出现在同一图像中的情况。
5.  **结果:** 该方法消除了**误报 (false positives)** 和**自匹配 (self-matching)** 问题，提供最准确的社会计量分析。

**使用场景:**
*   绘制一个人的社交圈。
*   分析一个人在什么环境以及与谁在一起。
*   揭示网络模式 (network patterns)。

**输出:**
*   相关人员列表（带有代表性人脸图像）。
*   每个相关人员的共同出现次数和群组大小。
*   分析统计数据（处理的人脸总数、唯一图像数等）。
*   可下载的 PDF 报告 (`/download/comprehensive_analysis_report`).

---

#### 2. 深度洞察 (Deep Insight)

分析特定人脸与系统中注册的其他通过人脸在同一照片中出现的频率。提供比综合人员分析更快的替代方案，但不执行基于相似度的对应分组。

**路由:** `/deep_insight/<face_id>`

**工作原理:**
1.  从 PostgreSQL (`ImageBasedMain` 表) 中检索包含目标人脸 (`face_id`) 的所有图像。
2.  列出在这些图像中与目标人脸一起发现的所有其他人脸。
3.  统计每个人脸与目标人脸在多少不同图像中共同出现。
4.  列出详细信息中最常出现的前 10 个人脸。

---

#### 3. 多种搜索模式

EyeOfWeb 提供各种搜索模式以满足不同需求。

##### a) 图像搜索 (Image Search)
**路由:** `/search/image`, `/search/upload`

将用户上传的照片中的人脸与数据库中的所有记录进行比对。
*   上传的图像通过安全检查。
*   使用 InsightFace 模型生成 512 维向量。
*   使用 `Cosine Similarity` 在 Milvus 数据库中搜索此向量。

##### b) 文本/过滤搜索 (Text/Filter Search)
**路由:** `/search`, `/search/text`

通过 PostgreSQL 对结构化数据（元数据）进行搜索。
*   `domain`: 过滤来自特定网站的结果。
*   `start_date` / `end_date`: 按检测日期范围过滤。
*   `risk_level`: 按风险等级过滤。
*   `category`: 按网站类别过滤。

##### c) 相似人脸搜索 (Similar Face Search)
**路由:** `/search/similar/<face_id>`

搜索与数据库中已注册的人脸 (`face_id`) 相似的其他人脸。

---

#### 4. 人脸检测与比对

##### a) 人脸检测 (Face Detection)
**路由:** `/face/detection`

检测上传图像中的所有人脸，显示边界框、性别、年龄和置信度分数。

##### b) 人脸比对 (Face Comparison)
**路由:** `/face/comparison`

分析两个不同上传图像中的第一张人脸是否匹配 (1:1 比对)。

---

#### 5. 多数据库集合

EyeOfWeb 支持多个 Milvus 集合和 PostgreSQL 表：

| 集合/表名称 (Collection / Table Name)           | 描述 (Description)                                                                 |
| :------------------------------- | :----------------------------------------------------------------------- |
| `EyeOfWebFaceDataMilvus`         |系统通过网络爬虫收集的主要人脸向量集合。        |
| `WhiteListFacesMilvus`           | 手动添加的“已识别”或“允许”人脸集合。|
| `ExternalFaceStorageMilvus`      | 从外部来源 (API 等) 传输的人脸。                             |
| `CustomFaceStorageMilvus`        | 用户定义的自定义集合。                                       |

---

#### 6. 管理仪表板 (Admin Dashboard)

**路由:** `/dashboard` (仅限管理员)

显示系统范围统计信息和健康状态的中央管理屏幕。

---

#### 7. PDF 报告系统

EyeOfWeb 可以为所有执行的分析（图像搜索、综合分析等）生成专业格式的 PDF 报告。

---

### 🏛️ 技术架构

---

#### 混合数据库系统 (PostgreSQL + Milvus)

EyeOfWeb 使用混合架构，分别处理结构化/关系型数据和高维向量数据。

| 组件          | 数据库       | 存储数据                                        | 用途                                                         |
| :------------ | :----------- | :---------------------------------------------- | :----------------------------------------------------------- |
| **记忆 (Memory)** | PostgreSQL   | 用户, URL 组件, 标题, 哈希, 日期, 风险等级      | SQL 查询, 过滤, 连接 (`JOIN`), 元数据                        |
| **大脑 (Brain)**  | Milvus       | 512-d 人脸向量, 212-d 地标向量                  | ANN 搜索 (HNSW), 相似度计算 (`Cosine Similarity`)            |

---

#### AI 引擎: InsightFace & AntelopeV2

EyeOfWeb 使用业界标准的 **InsightFace** 库和 **AntelopeV2** 模型。

**模型特性:**
*   **人脸检测:** RetinaFace
*   **向量大小:** 512 维
*   **属性:** 性别, 年龄, 眼镜, 质量分数

---

#### 安全基础设施

*   **身份验证:** Flask-JWT-Extended
*   **会话管理:** Flask-Session (Server-Side)
*   **加密:** Flask-Bcrypt
*   **CSRF 保护:** Flask-WTF
*   **速率限制 (Rate Limiting):** Flask-Limiter

---

### 🛠️ 技术栈 (Tech Stack)

| 层级 (Layer)               | 技术 (Technology)                                  | 版本/备注 (Version / Notes)             |
| :------------------- | :----------------------------------------- | :---------------------------- |
| **语言**              | Python                                     | 3.8+                          |
| **Web 框架**    | Flask                                      | 2.0+                          |
| **WSGI 服务器**      | Gunicorn / Waitress                        | 用于生产环境 (Production)    |
| **关系型数据库**     | PostgreSQL                                 | 13+                           |
| **向量数据库**        | Milvus                                     | 2.3+                          |
| **ML / AI**          | InsightFace (ONNX Runtime), NumPy, SciPy  | AntelopeV2 模型             |
| **图像处理**   | OpenCV (cv2), Pillow (PIL)                 |                               |
| **安全**         | Flask-JWT-Extended, Flask-Bcrypt           |                               |
| **网络爬虫**     | Selenium, Playwright                       | 异步/多标签支持 (Async/Multi-tab) |
| **前端**         | HTML5, CSS3, JavaScript, Jinja2            | 响应式 UI (Responsive UI)                 |
| **容器化**        | Docker, Docker Compose                     |                               |

---

### 📁 项目结构

```
eye_of_web/
├── .git/                           # Git version control
├── .gitignore                      # Files ignored by Git
├── LICENSE                         # MIT License
├── README.md                       # This documentation file
├── img/                            # Static images (logo, etc.)
│   └── logo.png
│
└── src/                            # Main source code directory
    ├── run.py                      # Flask application startup script
    ├── requirements.txt            # Python dependencies
    │
    ├── app/                        # Flask Application Module (MVC Architecture)
    │   ├── __init__.py             # Flask application factory
    │   ├── config/                 # Application configuration files
    │   ├── controllers/            # Business logic layer
    │   ├── models/                 # Database models / ORM
    │   ├── routes/                 # URL routing and endpoint definitions
    │   ├── static/                 # Static files (CSS, JS, images)
    │   └── templates/              # Jinja2 HTML templates
    │
    ├── config/                     # System configuration files
    │   ├── config.json             # GPU mode configuration
    │   └── cpu_config.json         # CPU mode configuration
    │
    ├── lib/                        # Helper libraries and tools
    │   ├── database_tools.py       # PostgreSQL & Milvus operations
    │   ├── init_insightface.py     # InsightFace model initialization
    │   └── pdf_generator.py        # PDF report generation
    │
    └── sql/                        # SQL schema and query files
```

---

### ⚙️ 安装指南

#### 系统要求

| 组件       | 最低要求                        | 推荐要求                             |
| :------------ | :----------------------------- | :----------------------------------- |
| **操作系统**        | Ubuntu 18.04+ / Windows 10 WSL2 | Ubuntu 20.04+ / Debian 11+          |
| **CPU**       | 4 核 (x86_64)            | 8+ 核 (AVX2 支持)          |
| **RAM**       | 8 GB                           | 16 GB 或更多                |
| **GPU**       | 可选                      | NVIDIA GPU (CUDA 11.x+), 4GB+ VRAM   |

#### 分步安装

**1. 系统依赖 (Ubuntu/Debian):**
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y python3-dev python3-pip python3-venv git \
    postgresql postgresql-contrib libpq-dev \
    build-essential libssl-dev libffi-dev \
    docker.io docker-compose
sudo systemctl enable docker && sudo systemctl start docker
```

**2. 克隆源代码:**
```bash
git clone https://github.com/MehmetYukselSekeroglu/eye_of_web.git
cd eye_of_web
```

**3. 创建 Python 虚拟环境:**
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r src/requirements.txt
```

**4. 启动 Milvus 数据库 (Docker):**
```bash
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml
sudo docker-compose up -d
```

**5. 配置 PostgreSQL:**
```bash
sudo systemctl start postgresql
sudo -u postgres psql << EOF
CREATE DATABASE eyeofweb;
CREATE USER eyeofwebuser WITH ENCRYPTED PASSWORD 'strong_password_here';
GRANT ALL PRIVILEGES ON DATABASE eyeofweb TO eyeofwebuser;
\q
EOF
```

**6. 生成数据库架构:**
```bash
python src/MILVUS_SCHEMA_GENERATOR.py
```

**7. 启动应用程序:**
```bash
python src/run.py
```
在浏览器中访问 `http://localhost:5000`。

---

### ⚙️ 配置选项

#### InsightFace (GPU/CPU) 配置

**`src/config/config.json` (GPU 模式):**
```json
{
  "insightface": {
    "prepare": {
      "ctx_id": 0,
      "det_thresh": 0.6,
      "det_size": [640, 640]
    },
    "main": {
      "providers": ["CUDAExecutionProvider"],
      "name": "antelopev2"
    }
  }
}
```

**`src/config/cpu_config.json` (CPU 模式):**
```json
{
  "insightface": {
    "prepare": {
      "ctx_id": -1,
      "det_thresh": 0.5,
      "det_size": [160, 160]
    },
    "main": {
      "providers": ["CPUExecutionProvider"],
      "name": "antelopev2"
    }
  }
}
```

---

### 📄 许可证

本项目基于 **MIT License** 许可。

请参阅项目根目录中的 `LICENSE` 文件以获取完整许可证文本。

---

### 🙏 致谢与贡献者

我们衷心感谢为本项目的实现做出贡献的人们。

---

#### 顾问 / 讲师 (Advisor / Instructor)

| | |
|---|---|
| **姓名** | **Uğur POLAT** |
| **贡献** | 学术指导、项目管理、架构愿景与技术咨询 |

---

#### 安全研究员 / Security Research

| | |
|---|---|
| **姓名** | **Enes Ülker** |
| **贡献** | 网络安全研究员 / Cyber Security Researcher |

---

#### 项目所有者 / 首席开发者 (Project Owner / Lead Developer)

| | |
|---|---|
| **姓名** | **Mehmet Yüksel ŞEKEROĞLU** |
| **贡献** | 全栈开发、AI 模型集成、数据库设计、系统架构与文档 |

---

### 📸 用户界面截图

| 屏幕 | 图像 |
|-------|---------|
| **欢迎屏幕** | ![Welcome Screen](img/welcome_screen.png) |
| **文本搜索输入** | ![Text Search Input](img/text_search_input.png) |
| **文本搜索结果** | ![Text Search Results](img/text_search_results.png) |
| **人脸搜索 - 添加图片** | ![Face Search Add Picture](img/face_serch_move_1_add_picture.png) |
| **人脸搜索 - 结果** | ![Face Search Results](img/face_search_move_2_results.png) |
| **人脸搜索 - 高级结果** | ![Face Search Advanced Results](img/face_search_move_3_advanced_results.png) |
| **人脸检测** | ![Face Detection](img/face_detection.png) |
| **人脸比对** | ![Face Comparison](img/face_comparsion.png) |
