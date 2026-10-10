# PaperAgent 最新版源码

本目录是一份可独立安装的 PaperAgent 前后端源码。仓库根目录原有版本仍可单独查看；以下命令都在 `PaperAgent_Lastest` 中执行。

## 包含内容

- `PaperQuery_Backend/`：FastAPI 接口、论文处理与向量索引、智能问答、研究任务编排、内置 Skills、测试与维护脚本。
- `PaperQuery_Frontend/`：Vue 3 工作区、页面、API 客户端和构建配置。
- `start_all.ps1`：Windows 本地启动脚本，启动 API、论文向量化 Worker 和前端开发服务器。

仓库不包含真实密钥、个人论文和数据库、运行日志、依赖目录或 BGE 等模型权重。首次使用需要自行配置模型服务密钥；初次生成论文向量时，Chroma 的 ONNX MiniLM 模型可能需要联网下载。扫描版 PDF 如无文字层，需要先做 OCR。

## Windows 本地运行

建议使用 Python 3.12、Node.js 18 以上版本和 PowerShell。以下命令从 `PaperAgent_Lastest` 目录开始：

```powershell
cd .\PaperQuery_Backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r req_win.txt
Copy-Item .env.example .env
```

编辑后端 `.env`，填入自己的 `DEEPSEEK_API_KEY`，并把 `SECRET_KEY` 改为随机长字符串。其他模型服务密钥按需填写。不要提交 `.env`。

```powershell
cd ..\PaperQuery_Frontend
npm ci
Copy-Item config\.env.example config\.env.dev
# 开发模式直连本地后端；生产部署可继续使用 /api
(Get-Content config\.env.dev) -replace "VITE_API_BASE_URL=/api", "VITE_API_BASE_URL=http://127.0.0.1:8001" | Set-Content config\.env.dev -Encoding utf8
cd ..
.\start_all.ps1
```

打开 `http://127.0.0.1:8080`。后端地址为 `http://127.0.0.1:8001`，就绪检查为 `http://127.0.0.1:8001/health/ready`。首次启动后端会创建本地 SQLite 数据库。可在登录页注册用户；如需管理员账号，请在后端数据库初始化后执行：

```powershell
cd .\PaperQuery_Backend
.\.venv\Scripts\python.exe -m scripts.create_admin
```

该命令会交互式读取管理员密码。不会创建预设密码。

## 可选功能与排查

- 论文入库和检索需要 `vector.py` Worker 持续运行；`start_all.ps1` 会同时启动它。若单独启动服务，请分别在后端目录运行 `python main.py` 和 `python vector.py`，并在前端目录运行 `npm run dev`。
- 离线英译中需要额外下载 Argos 语言包：在后端目录运行 `.\.venv\Scripts\python.exe -m scripts.install_offline_translation`。未安装时其余功能仍可启动。
- BGE-M3 和重排模型为可选本地增强检索；未提供权重时使用现有 ONNX 检索。若自行配置权重，参考后端 `core/common/config.py` 中的模型路径设置，并额外安装所需的 `sentence-transformers`。
- 如果前端页面能打开但接口请求失败，检查 `config/.env.dev` 中的 `VITE_API_BASE_URL` 是否为实际后端地址，并查看 `/health/ready`。
- Windows 依赖清单为 `PaperQuery_Backend/req_win.txt`。`requirement.txt` 包含其他平台和可选组件，不建议在 Windows 上直接安装。

生产构建可复制 `config/.env.example` 为 `config/.env.prod`，按部署地址修改 `VITE_API_BASE_URL`，再运行 `npm run build`。若使用 `/api`，请在反向代理中将该路径转发到后端 8001 端口。


## 2026-10-10 版本更新

- 全站蓝白设计、动态登录封面与单行品牌 slogan。
- 论文自定义名称；改进论文选择、PDF 选区高亮及论文内问答显示。
- 智能问答与深度研究完成时提供跨页面提醒。
- 今日推荐在本地归纳科研兴趣，仅向 arXiv/OpenAlex 发送检索关键词。
- 深度研究对比表渲染、Word 导出和复制；AI 回答支持独立复制。
- 完整前后端源码、依赖清单及必要静态资源；不包含真实 .env、运行数据与模型权重。
