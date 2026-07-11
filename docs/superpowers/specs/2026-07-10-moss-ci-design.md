# Moss CI — AI 智能体评测平台 设计文档

**日期**: 2026-07-10
**状态**: 设计中
**作者**: tongchun.zhao

---

## 1. 项目概述

### 1.1 定位

Moss CI 是一个**生产级 AI 智能体评测平台**，用于在 Moss 智能体每次变更后自动运行评测套件，检测行为退化（regression）。

和传统 CI/CD 不同，测试的不是"构建是否成功"，而是 **"AI 行为是否正确"**——评估结果不是二进制 pass/fail，而是多维度综合评分。

### 1.2 目标用户

公司内部所有开发和测试 Moss 的团队，任何人都可以提交测试任务。

### 1.3 核心能力

- 定义测试用例（YAML 文件 + Python SDK）
- 以多种方式运行测试（CLI、API、Webhook、定时任务）
- 对 Moss 输出进行多维度评估（断言、工具调用、LLM-as-Judge、副作用）
- 存储和对比历史结果，自动检测回归
- 检测 flake（AI 输出的随机性导致的不稳定测试）
- Web Dashboard 可视化

---

## 2. 系统架构

### 2.1 总览

```
┌──────────────────────────────────────────────────────────────┐
│                      用户入口                                 │
│              CLI  │  Webhook  │  API  │  Web Dashboard        │
├──────────────────────────────────────────────────────────────┤
│                      API Server (FastAPI)                     │
├──────────────────────────────────────────────────────────────┤
│                    Pipeline Engine (DAG 调度)                  │
│   ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐  │
│   │ 解析    │ → │ 编排    │ → │ 并行执行  │ → │ 收集结果  │  │
│   │YAML/SDK │   │DAG 拓扑 │   │ 多个Moss │   │ 汇总评估  │  │
│   └─────────┘   └─────────┘   └──────────┘   └──────────┘  │
├──────────────────────────────────────────────────────────────┤
│                      Executor Layer                           │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │  Moss Runner │  │  Evaluator   │  │  Artifact    │      │
│   │  (调用Moss)  │  │ (断言/LLM判断)│  │  Manager     │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
├──────────────────────────────────────────────────────────────┤
│                      Storage Layer                            │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │  PostgreSQL  │  │  MinIO/S3    │  │    Redis      │      │
│   │  (元数据)    │  │  (日志/产物) │  │  (队列/缓存)  │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 接口 |
|------|------|------|
| **Test Definition** | 定义测试用例 | YAML 文件 + Python SDK |
| **Pipeline Engine** | 解析→调度→执行 | 内部模块 |
| **Moss Runner** | 调用 Moss 智能体 | 统一接口，CLI/API/SDK 三种后端 |
| **Evaluator** | 评估 Moss 输出 | 5 种评估器，可插拔扩展 |
| **API Server** | 对外 REST API | FastAPI + SSE |
| **CLI** | 命令行入口 | Typer + Rich |
| **Web Dashboard** | 可视化界面 | React + 图表库 |
| **Storage** | 持久化 | PostgreSQL + MinIO + Redis |

---

## 3. 测试定义格式（YAML）

### 3.1 完整示例

```yaml
# suites/code_review.yaml
name: "代码审查能力回归"
description: "验证 Moss 的 PR review 能力没有退化"
version: "1.0"

config:
  moss:
    model: claude-sonnet-5
    timeout: 300
    retry: 2
  eval:
    judge_model: claude-opus-4-8

tests:
  # === 类型1: Prompt 断言 ===
  - name: "review-正确识别bug"
    moss:
      prompt: |
        请 review 以下 PR，指出存在的问题：
        ```java
        public void process(User user) {
            String name = user.getName();
            System.out.println(name.toUpperCase());
        }
        ```
    eval:
      - type: contains
        value: "null"
      - type: contains
        value: "NPE"
        mode: any

  # === 类型2: 工具调用验证 ===
  - name: "review-正确调用工具链"
    moss:
      prompt: "review https://github.com/org/repo/pull/42"
    eval:
      - type: tool_sequence
        expected:
          - tool: read_file
          - tool: read_diff
          - tool: create_comment
        order: strict
      - type: tool_args
        tool: create_comment
        contains:
          body: "建议"

  # === 类型3: LLM-as-Judge ===
  - name: "review-评论质量"
    moss:
      prompt: "review this PR and leave comments"
      context: "PR 改动：将 UserService 中的同步调用改为异步"
    eval:
      - type: llm_judge
        rubric: |
          请从以下维度评分（1-5分）：
          1. 评论是否指出了具体问题
          2. 建议是否可操作
          3. 语气是否友好专业
        threshold: 4.0
        dimensions:
          - name: "具体性"
            min: 3

  # === 类型4: 端到端场景 ===
  - name: "review-完整流程"
    moss:
      task: |
        1. 读取 src/utils.py
        2. 找出代码问题
        3. 修复问题
        4. 运行测试确保通过
      workdir: ./fixtures/repo
    eval:
      - type: side_effect
        check: "file_modified"
      - type: side_effect
        check: "tests_pass"
      - type: llm_judge
        rubric: "修复是否正确解决了问题，没有引入新问题"
        threshold: 4.0

  # === 类型5: 多轮对话 ===
  - name: "review-多轮交互"
    moss:
      conversation:
        - role: user
          content: "review 这个 PR"
        - role: assistant
          content: null
        - role: user
          content: "能更具体一点吗？"
        - role: assistant
          content: null
    eval:
      - type: llm_judge
        rubric: "第二轮回复是否比第一轮更具体、更有针对性"
        threshold: 4.0
        compare_to: round_1

  # === Flake 检测 ===
  - name: "review-正确性"
    flake_detection:
      runs: 3
      pass_threshold: 2
      consensus: majority
```

### 3.2 五种评估器

| 评估器 | 用途 | 判定方式 |
|--------|------|----------|
| `contains` | 文本内容匹配 | 输出是否包含预期字符串/正则 |
| `tool_sequence` | 工具调用顺序 | 是否按预期顺序调用了工具 |
| `tool_args` | 工具参数校验 | 工具调用参数是否包含指定内容 |
| `llm_judge` | 语义质量评估 | 用更强的模型按 rubric 打分 |
| `side_effect` | 副作用检查 | 文件是否被修改、测试是否通过 |

### 3.3 高级特性

- **模板变量**: 支持 `{{ model }}`、`{{ date }}` 等变量替换
- **继承**: suite 可以继承 base suite 的 config
- **条件执行**: `if: "{{ model }}" == "claude-sonnet-5"` 条件跳过
- **matrix 策略**: 一个 test 在多组参数下运行（如不同 model × 不同 temperature）
- **路径基准**: `workdir`、`context` 等文件路径，默认相对于 suite 文件所在目录

---

## 4. Pipeline Engine（调度引擎）

### 4.1 执行流程

```
Parse YAML → Build DAG → 拓扑排序 → 并行执行 → 收集结果
```

### 4.2 并行模型

- **Suite 级别并行**: 所有 suite 默认并行执行
- **Test 级别并行**: 每个 suite 内的 test 默认并行执行
- **并发控制**: 通过 `max_concurrency` 限制同时运行的 Moss 实例数

### 4.3 失败策略

- **fail-fast** (默认): 任一 test 失败立即停止
- **continue-on-error**: 收集所有结果后再判断
- **retry**: 网络错误自动重试，通过 `tenacity` 实现

### 4.4 Flake 检测

由于 LLM 输出有随机性，同一测试可能偶尔失败。Flake 检测机制：

```yaml
flake_detection:
  runs: 3                    # 跑 N 次
  pass_threshold: 2          # 至少 M 次通过
  consensus: majority        # 多数投票
```

结果标记为 `flake` 而非 `fail`，在 Dashboard 中单独展示。

### 4.5 回归分析

每次运行完成后，自动与上次运行结果对比：

- **新增失败**: 上次通过、本次失败的 test
- **修复**: 上次失败、本次通过的 test
- **改善**: LLM-as-Judge 评分上升超过阈值
- **退化**: LLM-as-Judge 评分下降超过阈值

---

## 5. Moss Runner（执行器）

### 5.1 统一接口

```python
class MossRunner:
    """所有 Moss 调用通过此接口，屏蔽 CLI/API/SDK 差异"""
    
    async def run(self, test: TestCase) -> MossResult: ...
    async def run_conversation(self, test: TestCase) -> MossResult: ...
    async def run_task(self, test: TestCase) -> MossResult: ...
```

### 5.2 三种后端

| 后端 | 实现方式 | 适用场景 |
|------|----------|----------|
| **SDK** | `import moss` 直接调用 | 最可靠，可获取完整 tool_call 数据 |
| **API** | HTTP 调用 Moss 服务 | 最灵活，适合远程 Moss 实例 |
| **CLI** | `subprocess` 调用 moss 命令 | 最简单，本地开发调试 |

自动检测可用后端：SDK > API > CLI。

### 5.3 关键行为

- **流式输出**: 实时收集并写入日志，同时保存完整输出供评估
- **超时控制**: 每个 test 独立超时，优雅中断（SIGTERM → SIGKILL）
- **并发控制**: 信号量限制同时调用的 Moss 实例数
- **环境隔离**: 每个 test 可指定 `workdir`、`env`、`model`

---

## 6. Evaluator（评估引擎）

### 6.1 流程

```
MossResult → 多个 Evaluator 并行评估 → 加权汇总 → PASS/FAIL + 详细报告
```

### 6.2 结果模型

```python
@dataclass
class TestResult:
    test_name: str
    status: Literal["pass", "fail", "error", "flake"]
    duration: float
    moss_output: str
    moss_tool_calls: list
    evals: list[EvalResult]
    flake_runs: list[TestResult] | None

@dataclass
class SuiteResult:
    suite_name: str
    total: int
    passed: int
    failed: int
    flake: int
    duration: float
    tests: list[TestResult]

@dataclass
class PipelineResult:
    pipeline_name: str
    suites: list[SuiteResult]
    summary: str
    diff: DiffResult | None
```

### 6.3 LLM-as-Judge 特殊处理

- **评委模型**: 必须比被测模型更强（默认 `claude-opus-4-8`）
- **校准**: 可选配置校准用例，减少评委自身偏差
- **多维度**: 支持分维度打分，各自设置阈值

---

## 7. API Server

### 7.1 核心端点

```
POST   /api/v1/pipelines/run              # 触发 pipeline 运行
GET    /api/v1/runs/{run_id}              # 查询运行状态
GET    /api/v1/runs/{run_id}/logs         # 实时日志 (SSE)
POST   /api/v1/runs/{run_id}/cancel       # 取消运行
GET    /api/v1/runs                       # 历史运行列表
GET    /api/v1/runs/{run_id}/diff         # 与上次运行对比
GET    /api/v1/suites                     # 列出测试套件
GET    /api/v1/suites/{name}/history      # 套件历史趋势
GET    /api/v1/runs/{run_id}/tests        # 测试结果列表
GET    /api/v1/runs/{run_id}/tests/{name} # 单个测试详情
```

### 7.2 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 异步原生、自动 OpenAPI 文档、类型安全 |
| 实时推送 | SSE | 比 WebSocket 简单，日志推送单向足够 |
| 后台任务 | asyncio + 任务队列 | 异步执行 pipeline，不阻塞 API |
| 认证 | OAuth2/OIDC | 内部工具对接公司 SSO |

---

## 8. CLI

```bash
# 核心命令
moss-ci run suites/                        # 运行所有 suite
moss-ci run suites/code_review.yaml        # 运行指定文件
moss-ci run --test "review-正确识别bug"     # 运行指定 test

# 查看结果
moss-ci status <run_id>                    # 查看运行状态
moss-ci logs <run_id>                      # 实时日志
moss-ci logs <run_id> --test "review-正确性" # 某个 test 的日志

# 历史与分析
moss-ci history                            # 最近运行列表
moss-ci diff <run_id_1> <run_id_2>        # 两次运行对比
moss-ci trend suites/code_review.yaml      # 趋势图（终端图表）

# 管理
moss-ci init                               # 初始化项目配置
moss-ci validate suites/                   # 校验 YAML 格式
```

---

## 9. 存储

| 存储 | 用途 | 内容 |
|------|------|------|
| **PostgreSQL** | 元数据 | 运行记录、评估结果、配置、用户 |
| **MinIO / S3** | 大文件 | 日志、产物、截图 |
| **Redis** | 热数据 | 任务队列、状态缓存、速率限制 |

### 9.1 核心表结构

```
pipelines        —  pipeline 定义
runs             —  每次运行记录
test_results     —  每个 test 的结果
evaluations      —  每个 evaluator 的详细评分
flake_results    —  flake 检测的各次运行结果
diffs            —  回归分析对比结果
suite_configs    —  套件配置
```

---

## 10. Web Dashboard

### 10.1 页面规划

| 页面 | 内容 |
|------|------|
| **首页** | 最近运行概览、通过率趋势、最近回归 |
| **运行详情** | 单次运行的完整报告，suite/test 级别 drill-down |
| **测试详情** | 单个 test 的 Moss 输出、评估结果、历史对比 |
| **趋势分析** | 某 suite 的历史趋势图、通过率变化 |
| **回归分析** | 自动标记新增失败/修复，按时间线展示 |
| **配置管理** | Moss 配置、评委模型、阈值管理 |

### 10.2 技术选型

| 组件 | 选择 |
|------|------|
| 前端框架 | React + TypeScript |
| 图表 | Recharts / ECharts |
| 构建 | Vite |

---

## 11. 项目结构

```
D:\moss-ci/
├── pyproject.toml
├── README.md
├── moss_ci/
│   ├── __init__.py
│   ├── cli/                    # CLI 入口
│   │   ├── __init__.py
│   │   └── main.py
│   ├── api/                    # FastAPI 服务
│   │   ├── __init__.py
│   │   ├── server.py
│   │   └── routes/
│   ├── engine/                 # Pipeline 引擎
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   ├── scheduler.py
│   │   └── executor.py
│   ├── runner/                 # Moss Runner
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── sdk.py
│   │   ├── api.py
│   │   └── cli.py
│   ├── evaluator/              # 评估引擎
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── contains.py
│   │   ├── tool_sequence.py
│   │   ├── tool_args.py
│   │   ├── llm_judge.py
│   │   └── side_effect.py
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   ├── test.py
│   │   └── result.py
│   ├── storage/                # 存储层
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── object_store.py
│   │   └── cache.py
│   └── web/                    # Web Dashboard
│       ├── __init__.py
│       ├── src/
│       └── ...
├── tests/                      # moss-ci 自身测试
├── examples/                   # 示例 YAML
│   ├── simple_assert.yaml
│   ├── tool_check.yaml
│   ├── llm_judge.yaml
│   └── e2e_scenario.yaml
└── docs/
    └── superpowers/
        └── specs/
```

---

## 12. 技术依赖

```toml
[project]
name = "moss-ci"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]",
    "pydantic>=2",
    "pyyaml",
    "httpx",
    "asyncpg",
    "sqlalchemy[asyncio]",
    "alembic",
    "redis[hiredis]",
    "boto3",
    "rich",
    "typer",
    "sse-starlette",
    "structlog",
    "tenacity",
    "networkx",
]
```

---

## 13. 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 语言 | Python | AI 生态、与 Moss 同栈、开发效率 |
| 用例定义 | YAML 为主，Python SDK 为辅 | 非技术人员可写，版本控制友好 |
| 并行粒度 | Suite 和 Test 两级并行 | 最大化并发 |
| 存储 | PostgreSQL + MinIO + Redis | 元数据、大文件、热数据分离 |
| 实时推送 | SSE | 比 WebSocket 简单，满足需求 |
| 评委模型 | 可配置，默认比被测模型强 | 评审公平性 |
| Flake 检测 | 重跑 N 次 + 多数投票 | AI 输出随机性的必要处理 |