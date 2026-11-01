# 部署边界

> 结论先说：**本项目的代码执行依赖 Docker。** 没有 Docker 的托管环境（当前
> `render.yaml` 的 Render 免费实例）只能提供聊天/检索/画像，练习提交会返回
> "未判定"。这不是 bug，是沙箱边界的设计（`APP_ENV=production` 强制隔离）。

## 1. 三种运行环境

| 环境 | 数据库 | 学生代码执行 | 适用 |
|------|--------|--------------|------|
| 本地开发 | SQLite | 有 Docker 走 Docker；没有则宿主进程（`SANDBOX_MODE=auto`） | 开发、测试、答辩演示 |
| 自托管（Docker Compose） | PostgreSQL | 容器内执行（`auto` 无嵌套 Docker 时退到宿主进程） | 内网/单机演示 |
| Render + Vercel | SQLite（临时磁盘） | **不可用**：没有 Docker，生产强制隔离 → `unavailable` | 只做聊天/RAG 展示 |

## 2. Render 部署的实际行为

`render.yaml` 设置 `APP_ENV=production`。按
`sandbox/runner.py` 的规则，此时 `isolation_required=True`；Render 不提供
Docker，因此：

- 聊天、RAG、画像、教师看板正常；
- 练习提交返回 `status="unavailable"`，不判题、不写画像、不发奖励；
- 前端会显示"未判定"，不会假装通过。

另外，Render 免费实例的磁盘是临时的，SQLite 数据在重启/重新部署后会丢失。
若要在公网长期使用，需要换成托管 PostgreSQL，并解决 Docker 沙箱。

## 3. 需要完整演示（含判题）时

在**有 Docker 的机器**上：

```bash
# 1) 起数据库和后端（开发 compose 已包含 Postgres）
docker compose up -d postgres
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2) 前端
cd frontend && npm run build && npm run start
```

或直接在宿主机跑后端（`SANDBOX_MODE=auto` + 本机 Docker），这也是答辩演示的
推荐路径：可靠性最高，且判题链路完整。

## 4. 生产数据库

`APP_ENV=production` 时不执行 `create_all()`，必须：

```bash
cd backend
alembic upgrade head
```

迁移链已在 CI 中用空库验证（`ci_migrate.db`），会建出包括
`weak_topics` / `recent_misconceptions` / `hint_dependency` / `completed_lessons`
在内的完整 `student_profiles`。

## 5. 限流

进程内限流默认开启（`RATE_LIMIT_ENABLED=true`）：

- 普通 API：`RATE_LIMIT_PER_MINUTE=120` / IP / 分钟
- 注册登录：`AUTH_RATE_LIMIT_PER_MINUTE=10` / IP / 分钟

多 worker / 多实例时每个进程各算一份，真实上限是配置 × 进程数。公网部署应换成
Redis 或网关限流；本实现只用于单实例和开发环境。

### 5.1 客户端 IP 与反向代理

限流按客户端 IP 计数。`X-Forwarded-For` **默认不信任**（`TRUST_PROXY_HEADERS=false`）：
客户端可以任意伪造该头，信任它等于让人一条请求换一个 IP 绕过限流。

只有把服务放在自己控制的反向代理后面（Render/Render Cron、Nginx、Cloudflare 等会覆盖
而不是透传该头）时才设 `TRUST_PROXY_HEADERS=true`。判断方法：直连端口时伪造
`X-Forwarded-For` 必须**不能**改变限流结果（`backend/tests/test_rate_limit.py` 有对应用例）。

### 5.2 生产配置校验

`APP_ENV=production` 时启动期会拒绝以下配置（`config.py` 的 `_validate_production`）：

- `DEBUG=true`
- `SECRET_KEY` 为空、弱值或短于 32 字符

另外生产环境不再把异常详情写进 500 响应和 `/health` 的 `error` 字段，lifespan 初始化
异常会直接终止启动（不再 `try/except` 吞掉）。

## 6. 不可宣称

- "生产级安全"：沙箱只在单机 Docker 下验证过，没有做逃逸测试/资源上限压测。
- "Render 上可完整运行"：当前配置下判题不可用。
- "多实例可用"：限流、内存态检索索引都不是跨实例共享的。
