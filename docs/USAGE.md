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

- **moss-ci 工具**在 `D-Robotics/moss-ci`（pip install 拉取）
- **能力测试套件**在 ci_test 的 `examples/moss_capabilities.yaml`
- **CI workflow**在 Moss fork（`1-ztc/moss`）的 `.github/workflows/moss-ci.yml`
- **API key**在 Moss fork 的 GitHub Secret `MOSS_API_KEY`

### 在 Moss fork 激活 CI

参考 workflow 在 `D-Robotics/moss-ci` 的 `.github/workflows/moss-ci.yml`。把它复制到 `<moss-fork>/.github/workflows/moss-ci.yml`，然后在 fork 的 Settings → Secrets → Actions 加 `MOSS_API_KEY`（值是 Moss 模型的 apiKey）。

### CI 工作流

push 到 `main` 或 `2026_*` 分支 / 开 PR 时触发：

1. 构建 Moss（`npm run build --workspace @rdk-moss/agent`）
2. `pip install` moss-ci from `D-Robotics/moss-ci`
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

要让 F1（llm_judge）真打分，再加两个 secret：
- `MOSS_CI_JUDGE_API_URL` = judge 的 Anthropic-协议 endpoint（horizon 用 `https://llmapi.horizon.auto`）
- `MOSS_CI_JUDGE_API_KEY` = judge 的 apiKey

judge 走 Anthropic `/v1/messages` 协议：endpoint host 非 `api.anthropic.com` 时自动用 `Authorization: Bearer`（对齐 Moss fork 的 Bearer 检测），官方 Anthropic 仍用 `x-api-key`。模型默认 `HORIZON-GLM`（可按 eval 用 `model:` 覆盖）。**未配** URL/key 时该 eval 标 error、F1 报 fail——不会造假分假装通过。

## 能力测试套件

`examples/moss_capabilities.yaml`（v2.0）是工业级套件，13 个测试覆盖 Moss 作为 agent 的 6 个能力维度。每个评估值都是"只有 Moss 真调工具/真推理/真改文件才能答对"的内容。

### 13 个测试（分两层）

**快速层（tag: quick）—— 每次 push/PR 跑，~2-3 分钟**

| 测试 | 评估器 | 测什么 |
|---|---|---|
| A1 read_file 调用与参数 | tool_sequence + tool_args | 调 read_file 且 path 含 secret_config |
| A2 write_file 调用与参数 | tool_sequence + tool_args | 调 write_file 且 path 对 |
| A3 多工具序列 read→write | tool_sequence (strict) | read_file 后跟 write_file 的顺序 |
| D1 代码bug-除零 | contains (regex) | 找出除零 bug |
| D2 代码bug-空值处理 | contains (regex) | 找出空列表索引 bug |
| D3 多步推理-列表计数 | contains | 读文件 + 数数组长度 |
| E1 简单回答稳定性 | flake (3次) | 输出忽好忽坏会被标 flake |
| E2 信息提取稳定性 | flake (3次) | 读文件能力稳定性 |
| F1 代码review质量 | llm_judge | LLM 按 rubric 打分（需配 `MOSS_CI_JUDGE_API_URL`+`MOSS_CI_JUDGE_API_KEY`）|

**完整层（tag: full）—— 手动 workflow_dispatch / 夜间跑，~10+ 分钟**

| 测试 | 评估器 | 测什么 |
|---|---|---|
| B1 写文件副作用 | side_effect file_modified | 写文件 + files_modified 抓取 |
| B2 改文件副作用 | side_effect file_modified | 改已有文件 |
| **C1 自主修bug端到端** | side_effect tests_pass (flake 3次) | **Moss 自主完成 读代码→找bug→edit_file修→跑pytest→确认** |
| C2 读-处理-写链路 | side_effect file_modified (flake 3次) | 读文件A→提取→写文件B |

### 5 种评估器全用上

| 评估器 | 测什么 | 用在哪 |
|---|---|---|
| `contains` | 输出含某文本（支持 regex） | D1/D2/D3 |
| `tool_sequence` | 工具调用顺序 | A1/A2/A3/B1 |
| `tool_args` | 工具参数正确 | A1/A2 |
| `side_effect` | 副作用（file_modified/tests_pass）| B1/B2/C1/C2 |
| `llm_judge` | LLM 当评委打分（Anthropic 协议, Bearer） | F1（需 `MOSS_CI_JUDGE_API_URL`+`MOSS_CI_JUDGE_API_KEY`）|

### 工具调用 + 文件改动抓取

CLIBackend 跑完 Moss 后读其 session jsonl（`<cwd>/.moss/sessions/*.jsonl`），提取：
- **tool_calls**：Anthropic 风格 `tool_use` 块（`{"name":...,"input":...}`）→ moss-ci 格式 `{"tool":...,"args":...}`
- **files_modified**：write_file/edit_file/apply_patch/move_file 的 input.path

只解析本次新增的 session（跑前 snapshot，跑后取差集），历史不污染。

### 端到端验证结果

本地用真实 Moss（deepseek-v4-pro）验证全部 13 个测试可过：

- **快速层**：9 个全 pass（含工具调用、代码理解、稳定性、质量）
- **完整层**：4 个全 pass，含 **C1 自主修 bug 跑 3 次全 pass**（Moss 每次都完整完成 读→找→edit_file→跑pytest→报告"tests pass"）

> C1 的关键修复：`side_effect tests_pass` 改成不区分大小写匹配 "pass"（Moss 说 "4 tests pass" 而非 pytest 的 "PASSED" 大写标志）。maxTurns 不是瓶颈（Moss 修 bug 只要 ~5 个工具调用，默认 64 轮够）。

## 写自己的测试

照 `examples/moss_capabilities.yaml` 抄。关键点：
- `contains` 的值选 **Moss 只能靠真本事答对**的东西（随机 token、文件字段），别用套话题
- prompt **不含答案**（否则 Moss 能从 prompt 抄，测不到真本事）
- 多步端到端用 `task:` 模式（Moss autonomous 跑）+ `tags: [full]`（放完整层）
- 关键测试加 `flake_detection: {runs: 3, pass_threshold: 2, consensus: majority}` 抓输出不稳定

```yaml
tests:
  - name: "my-test"
    tags: [quick]              # quick=每次push跑, full=手动/夜间
    moss:
      prompt: "..."            # 不含答案
      workdir: ./path/to/fixtures
    eval:
      - type: contains
        value: "<only-right-if-Moss-really-works>"
    flake_detection:            # 可选：跑3次抓不稳定
      runs: 3
      pass_threshold: 2
      consensus: majority
```
