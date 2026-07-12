# Moss CI 使用指南

moss-ci 是给 Moss 智能体做自动化回归评测的工具。这份指南讲怎么本地跑、怎么接 CI、怎么接自定义模型、怎么看回归 diff。

## 快速开始（本地）

### 前置

- Python 3.11+，装好 moss-ci：`pip install -e ".[dev]"`（开发）或 `pip install moss-ci`
- 一个能调用的 Moss（CLI/API/SDK 任一）

### 三步跑

```bash
cd /path/to/moss-ci

# 1. 设环境变量（每开一个新终端都要设）
export PYTHONUTF8=1                                          # Windows 必需，否则输出 ✓ 崩
export MOSS_CLI_COMMAND='node /path/to/moss/dist/cli.js --config-file /path/to/moss/config.json'

# 2. 跑能力测试
moss-ci run examples/moss_capabilities.yaml --no-fail-fast

# 3. 跑第二次后，对比两次（核心价值：看退步没）
moss-ci history                    # 列出所有 run，拿到两个 run_id
moss-ci diff <prev_run_id> <curr_run_id>
```

### 命令速查

| 命令 | 作用 |
|---|---|
| `moss-ci validate <suite.yaml>` | 检查 suite 格式（不调 Moss） |
| `moss-ci run <suite.yaml> [--no-fail-fast] [--mock]` | 跑测试（默认调真 Moss，`--mock` 用假输出） |
| `moss-ci history [-n 20]` | 列历史 run |
| `moss-ci status <run_id>` | 看某次 run 每个测试结果 |
| `moss-ci logs <run_id> [--test <name>]` | 看 Moss 原始输出 |
| `moss-ci diff <prev> <curr>` | 对比两次 run（DB 里的） |
| `moss-ci export [run_id] -o file.json` | 导出 run 成 JSON（省略 run_id 导最新） |
| `moss-ci diff-files prev.json curr.json` | 对比两个导出的 JSON |

## CI 接入（GitHub Actions）

CI 让"改 Moss → push → 自动跑能力测试 → 看退步没"全自动。架构：

- **moss-ci 工具**在 `1-ztc/ci_test`（pip install 拉取）
- **能力测试套件**在 ci_test 的 `examples/moss_capabilities.yaml`
- **CI workflow**在 Moss fork（`1-ztc/moss`）的 `.github/workflows/moss-ci.yml`
- **API key**在 Moss fork 的 GitHub Secret `MOSS_API_KEY`

### 在 Moss fork 激活 CI

参考 workflow 在 `1-ztc/ci_test` 的 `.github/workflows/moss-ci.yml`。把它复制到 `<moss-fork>/.github/workflows/moss-ci.yml`，然后在 fork 的 Settings → Secrets → Actions 加 `MOSS_API_KEY`（值是 Moss 模型的 apiKey）。

### CI 工作流

push 到 `main` 或 `2026_*` 分支 / 开 PR 时触发：

1. 构建 Moss（`npm run build --workspace @rdk-moss/agent`）
2. `pip install` moss-ci from `1-ztc/ci_test`
3. 拉能力测试套件 + fixture（从 ci_test 仓库 clone examples）
4. 从 `MOSS_API_KEY` secret 生成临时 config.json（key 不进仓库/日志）
5. 跑能力测试（真实调 Moss）
6. restore 上次 run 的结果（GitHub cache，per-branch）
7. export 当前 run + `diff-files` → 写到 job summary（PR Checks 页可见）
8. cache 当前结果作为下次 baseline

**首次 run** 建 baseline（summary 显示 "first run on this branch"）。**后续 run** 自动报 new_failure/fixed。

### 跨次回归 diff

job summary 里的 diff 报告是 CI 的核心价值：

- `No changes` — Moss 没退化，可合并
- `⚠ new_failure` — 哪个能力从 pass 变 fail，**精确定位退化点**
- `✓ fixed` — 之前坏的修好了
- `↑/↓ improved/degraded` — LLM 打分涨/跌（需配 judge）

## 接入自定义模型（如 horizon）

Moss 默认配 deepseek 等。要接自定义 Anthropic-协议 endpoint（如 `https://llmapi.horizon.auto`），需要：

### 1. 写 Moss config.json

```json
{
  "provider": "anthropic",
  "model": "<your-model-name>",
  "baseUrl": "https://your-endpoint.example",
  "apiKey": "<your-api-key>"
}
```

⚠️ **这个文件含 key，绝不提交仓库**。放本地或 CI secret。

### 2. Bearer auth 支持

官方 Anthropic API（`api.anthropic.com`）用 `x-api-key` 认证。但很多 Anthropic-协议网关（自定义 baseUrl）用 `Authorization: Bearer`。Moss 原本只发 `x-api-key`，对这些网关返回 401。

Moss fork 的 `2026_07_08` 分支加了自动检测：**baseUrl 不是 `api.anthropic.com` 时改用 Bearer**。改了两处：
- `packages/moss-agent/src/provider/anthropic.ts`（provider 层）
- `packages/moss-agent/src/cli/providers.ts` 的 `callAnthropic`（CLI 实际用的路径）

真 Anthropic 认证不受影响（仍是 `x-api-key`）。

### 3. 本地验证

```bash
# 直接调 Moss，确认模型接通
node /path/to/moss/dist/cli.js --config-file /path/to/config.json "Reply with: ok"

# 通过 moss-ci 调（含工具调用抓取）
export MOSS_CLI_COMMAND='node /path/to/moss/dist/cli.js --config-file /path/to/config.json'
moss-ci run examples/moss_capabilities.yaml --no-fail-fast
```

### 4. CI 上接自定义模型

在 Moss fork 的 Settings → Secrets 加：
- `MOSS_API_KEY` = 你的 key

workflow 的 "Write Moss model config from secret" 步骤生成 config.json。如果模型/provider/baseUrl 不是默认的 deepseek，改 workflow 那一步的 JSON 模板（`provider`/`model`/`baseUrl` 字段）。

## 能力测试套件

`examples/moss_capabilities.yaml` 测 Moss 的真实能力，每个评估值都是"只有 Moss 真调工具/真推理才能答对"的内容。

### 测的能力

| 测试 | 评估器 | 测什么 |
|---|---|---|
| 读取文件-提取字段 | contains | read_file + 信息提取 |
| 读取文件-提取随机token | contains | 同上（随机值蒙不出）|
| 代码bug-除零错误 | contains (regex) | 代码理解 + 缺陷识别 |
| 多步推理-列表计数 | contains | 多步组合（读 + 数）|
| 稳定性-3次 | flake 检测 | 输出稳定性 |
| 工具调用-顺序与参数 | tool_sequence + tool_args | 工具调用顺序 + 参数 |

### 5 种评估器

| 评估器 | 测什么 | 状态 |
|---|---|---|
| `contains` | 输出含某文本（支持 regex） | ✓ 已用 |
| `tool_sequence` | 工具调用顺序 | ✓ 已用（从 Moss session jsonl 提取）|
| `tool_args` | 工具参数正确 | ✓ 已用 |
| `side_effect` | 副作用（文件/退出码/测试）| 可用 |
| `llm_judge` | LLM 当评委打分 | 需配 `MOSS_CI_JUDGE_API_URL` |

### 工具调用抓取

`tool_sequence`/`tool_args` 依赖结构化工具调用。CLIBackend 跑完 Moss 后读其 session jsonl（`<cwd>/.moss/sessions/*.jsonl`），提取 Anthropic 风格的 `tool_use` 块（`{"name":...,"input":...}`），转成 moss-ci 格式 `{"tool":...,"args":...}`。只解析本次新增的 session，历史不污染。

## 写自己的测试

照 `examples/moss_capabilities.yaml` 抄。关键：`contains` 的值选**Moss 只能靠真本事答对**的东西（随机 token、文件里的特定字段），别用套话题。

```yaml
tests:
  - name: "my-test"
    moss:
      prompt: "..."
      workdir: ./path/to/fixtures   # 可选，相对 moss-ci cwd
    eval:
      - type: contains
        value: "<only-right-if-Moss-really-works>"
```
