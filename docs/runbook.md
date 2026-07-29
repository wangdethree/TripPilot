# 本地运行与演示手册

## 最快演示

```bash
cp .env.example .env
uv sync
uv run uvicorn trippilot.interfaces.http.app:create_app --factory --reload
```

另开终端：

```bash
cd web
npm ci
npm run dev
```

打开 `http://localhost:5173`，输入：

```text
2030-10-02 去成都玩两天，两个人，预算 3000 元，喜欢历史和美食
```

补充“预算不包含住宿”，确认后可查看两日计划、预算、约束和来源。

## Docker Compose

```bash
docker compose up --build
```

打开 `http://localhost:8080`。Compose 会启动 PostgreSQL、执行 Alembic 迁移、启动后端与 Nginx 前端。演示运行时默认 Fake 模式。

## 真实模型和工具

在 `.env` 或部署平台 Secret 中配置：

```text
TRIPPILOT_MODEL_PROVIDER=openai
TRIPPILOT_OPENAI_API_KEY=...
TRIPPILOT_TOOL_PROVIDER=real
TRIPPILOT_AMAP_API_KEY=...
```

真实天气预报有供应商可预报天数限制，演示日期应位于当前预报窗口。不要把密钥写进 Compose、代码、测试或截图。

## 质量门禁

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv run trippilot-eval
uv run alembic upgrade head --sql > /dev/null
npm run typecheck --prefix web
npm run build --prefix web
```

## 常见问题

### 前端显示请求失败

确认后端运行在 `127.0.0.1:8000`。Vite 会代理 `/api`；生产 Nginx 会代理到 Compose 的 `backend` 服务。

### OpenAI 模式启动失败

检查 `TRIPPILOT_OPENAI_API_KEY`。项目不会在缺少密钥时静默回退到 Fake，以免把演示数据误认为真实结果。

### 真实工具模式启动失败

高德地点查询需要 Web 服务 Key。Open‑Meteo 天气无需个人 Key，但真实模式仍要求高德 Key 才能保证地点数据来源。

### 日期被拒绝

日期不能早于当前日期，旅行长度第一版限制为 1～3 日。

### 如何清理匿名行程

前端未长期保存服务端 Token。API 支持使用 plan token 调用 `DELETE /api/v1/plans/current`。本地进程重启后内存任务和行程会消失。
