# API Plan Monitor

API 套餐用量监控工具，支持多平台 API 额度查询。

## 功能特性

- 支持 MiniMax、智谱 AI、Codex (ChatGPT) 等平台的套餐查询
- 提供 CLI 命令行工具和 FastAPI 服务
- 支持配置外部化，敏感信息通过 config.toml 管理
- 返回格式兼容 OpenRouter 订阅工具

## 项目结构

```
api_plan_monitor/
├── api_server.py         # FastAPI 服务
├── plan_monitor.py       # CLI 工具
├── config.toml          # 配置文件（敏感信息）
├── config.example.toml  # 配置文件示例
└── cookies/             # Cookies 文件目录
    ├── minimax_cookies.json
    ├── zhipu_cookies.json
    └── codex_cookies.json
```

## 快速开始

### 1. 安装依赖

```bash
pip install fastapi uvicorn requests toml
```

或使用 uv：

```bash
uv pip install fastapi uvicorn requests toml
```

### 2. 配置

复制配置示例文件：

```bash
cp config.example.toml config.toml
```

编辑 `config.toml`，填入你的配置：

```toml
[minimax]
api_url = "https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains"
group_id = "你的GroupId"
cookies_file = "cookies/minimax_cookies.json"
model_filter = "M2.5"

[glm]
api_url = "https://bigmodel.cn/api/monitor/usage/quota/limit"
cookies_file = "cookies/zhipu_cookies.json"

[codex]
api_url = "https://chatgpt.com/backend-api/wham/usage"
cookies_file = "cookies/codex_cookies.json"
```

### 3. 获取 Cookies

#### MiniMax

1. 登录 [MiniMax 平台](https://platform.minimaxi.com)
2. 打开浏览器开发者工具 (F12)
3. 找到 `HERTZ-SESSION` cookie 值
4. 导出完整 cookies 为 JSON 格式，保存到 `cookies/minimax_cookies.json`

#### 智谱 AI

1. 登录 [智谱平台](https://bigmodel.cn)
2. 打开浏览器开发者工具 (F12)
3. 找到 `bigmodel_token_production` cookie 值
4. 导出完整 cookies 为 JSON 格式，保存到 `cookies/zhipu_cookies.json`

#### Codex (ChatGPT)

1. 登录 [ChatGPT](https://chatgpt.com)
2. 打开浏览器开发者工具 (F12)
3. 找到 `__Secure-next-auth.session-token` 和 `cf_clearance` cookie 值
4. 导出完整 cookies 为 JSON 格式，保存到 `cookies/codex_cookies.json`

> **注意**: Codex 需要 `cf_clearance` cookie，该 cookie 有 Cloudflare 防护验证，时效较短，可能需要定期更新。

### 4. 运行

#### CLI 模式

```bash
# 查询所有平台
python plan_monitor.py -a

# 查询指定平台
python plan_monitor.py -p minimax
python plan_monitor.py -p glm
python plan_monitor.py -p codex

# 列出可用平台
python plan_monitor.py -l
```

#### API 服务模式

```bash
# 启动服务（仅本机访问）
python api_server.py
```

服务启动后访问：
- `http://127.0.0.1:8000/` - API 概览
- `http://127.0.0.1:8000/minimax/user/balance` - MiniMax 套餐
- `http://127.0.0.1:8000/glm/user/balance` - 智谱 AI 套餐
- `http://127.0.0.1:8000/codex/user/balance` - Codex (ChatGPT) 套餐

## API 返回格式

```json
{
  "isValid": true,
  "is_active": true,
  "balance": 96.73,
  "remaining": 96.73,
  "unit": "USD",
  "planName": "MiniMax M2.5 套餐",
  "total": 1500,
  "used": 49,
  "extra": "周期: 15:00 - 20:00 (UTC+8), 已用3%, 4小时43分钟后重置"
}
```

字段说明：
- `isValid`: 套餐是否有效
- `is_active`: 是否激活
- `balance`: 剩余百分比
- `remaining`: 剩余百分比（同 balance）
- `unit`: 单位（统一为 USD 便于订阅工具识别）
- `planName`: 套餐名称
- `total`: 总配额
- `used`: 已使用额度
- `extra`: 扩展信息

## 添加新平台

在 `config.toml` 中添加新平台配置：

```toml
[openai]
api_url = "https://api.openai.com/v1/usage"
cookies_file = "cookies/openai_cookies.json"
```

并在 `api_server.py` 和 `plan_monitor.py` 中添加对应的解析函数。

## License

MIT

---

## Consulting & Engineering · 咨询与工程交付

**EN** — Taking on a small number of engagements, from a scoped advisory review to a full delivery embedded in your team.

- **LLM and RL systems** — model selection and evaluation, training and fine-tuning pipelines, reward design and policy training, and the measurement that decides whether a result holds: perturbation audits, replication, effect sizes instead of anecdotes.
- **Agents you run yourself** — agent systems deployed on your own hardware or inside your VPC. Local inference on Apple Silicon (MLX) and on GPU servers, tool and MCP integration, call recording and replay, budget and failure accounting.
- **Forward-deployed engineering (FDE)** — embedded with your team for a defined term, carrying a problem from the first conversation to something running in your production, then handing over the code, the tests and the documentation.

**中文** — 只承接少量合作，从一次限定范围的方案评审，到嵌入团队的完整交付。

- **LLM 与强化学习算法咨询** — 模型选型与评测、训练与微调流水线、奖励设计与策略训练，以及决定结论能否成立的那部分工作：扰动审计、重复实验、用效应量而不是个案说话。
- **本地与私有化 Agent 部署** — 在你自己的机器或 VPC 里落地的 agent 系统。Apple Silicon（MLX）与 GPU 服务器上的本地推理、工具与 MCP 接入、调用录制与回放、预算与失败核算。
- **驻场交付工程（FDE）** — 以明确周期嵌入你的团队，把一个问题从第一次对话推到在你的生产环境里跑起来，并交付代码、测试与文档。

Contact · 联系方式：[misakaikato@outlook.com](mailto:misakaikato@outlook.com)
