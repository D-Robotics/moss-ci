# moss-ci 项目状态

> 这份文档记录 moss-ci 能力回归 CI 体系的现状,方便接手 / 新会话快速上手。
> 详细用法见 `USAGE.md`;这份是"现在到哪了"的快照。

## 两个仓库的关系

| 仓库 | 地址 | 角色 | 关键分支 |
|---|---|---|---|
| **ci_test** | github.com/1-ztc/ci_test | moss-ci 工具 + 能力测试套件 | `feat/implementation`（PR #1）|
| **moss fork** | github.com/1-ztc/moss | Moss 源码 fork + CI workflow | `2026_07_08`（上游: D-Robotics/moss,只读）|

- ci_test 是**测试工具**:CLI + 5 评估器 + diff + flake + export/diff-files
- moss fork 是**被测对象**:Moss 源码 + `.github/workflows/moss-ci.yml`(CI workflow)
- CI 运行时从 ci_test `pip install` moss-ci + clone examples,在 moss fork 上跑

## 本地工作区

- `D:\moss-ci` — moss-ci 工具开发(`.venv` 已装好),单元测试 `pytest`
- `D:\moss-from-remote` — Moss fork 源码,`2026_07_08` 分支,remote `origin`=你的 fork,`upstream`=D-Robotics/moss

## CI 体系现状

- **能力测试套件**:`examples/moss_capabilities.yaml`(v2.0),13 个测试分两层
  - quick(每次 push/PR):9 个单轮单工具测试
  - full(手动 workflow_dispatch / 夜间 schedule):4 个多步端到端
- **5 评估器全用上**:contains / tool_sequence / tool_args / side_effect / llm_judge
- **跨次回归 diff**:per-layer cache(`moss-ci-last-<branch>-<layer>` key),PR summary 显示 new_failure/fixed
- **分支保护**:已开 `2026_07_08` 的 "Require status checks",check 名 `Moss capability tests`(稳定名,见下),过 CI 才能合
- **分层触发**:push/PR → quick;workflow_dispatch + 夜间 03:17 UTC → full

## 关键文件位置

- 能力测试套件:`D:\moss-ci\examples\moss_capabilities.yaml` + `examples\fixtures/`(buggy.py, test_buggy.py, secret_config.json, to_transform.txt)
- CI workflow(两份同步):`D:\moss-ci\.github\workflows\moss-ci.yml` + `D:\moss-from-remote\.github\workflows\moss-ci.yml`
- Moss 模型配置(含 key,**已 gitignore**):`D:\moss-from-remote\.moss\config.json`(provider=anthropic/openai_compatible, model=deepseek-v4-pro)
- 使用文档:`D:\moss-ci\docs\USAGE.md`(ci_test)+ `D:\moss-from-remote\docs\agent-ci.md`(moss fork)

## 怎么跑(本地)

```bash
cd /d/moss-ci
export PYTHONUTF8=1                                          # Windows 必需
export MOSS_CLI_COMMAND='node D:/moss-from-remote/packages/moss-agent/dist/cli.js --config-file D:/moss-from-remote/.moss/config.json'

moss-ci run examples/moss_capabilities.yaml --tag quick --no-fail-fast   # 快速层
moss-ci run examples/moss_capabilities.yaml --tag full  --no-fail-fast    # 完整层(慢)
moss-ci history                    # 列历史 run
moss-ci diff <prev_id> <curr_id>   # 对比两次
```

## Moss fork 上的改动(相对上游 D-Robotics/moss)

- `packages/moss-agent/src/provider/anthropic.ts` + `src/cli/providers.ts`:Bearer auth 检测(baseUrl 非 api.anthropic.com 时用 Bearer,支持自定义 Anthropic-协议网关如 horizon)
- `.github/workflows/moss-ci.yml`:能力回归 CI(两层 + cache diff)
- `docs/agent-ci.md`:CI 说明文档

## GitHub Secrets(moss fork)

- `MOSS_API_KEY` — Moss 模型的 apiKey
- `MOSS_CI_JUDGE_API_URL` — llm_judge 的 Anthropic-协议 endpoint(horizon 用 `https://llmapi.horizon.auto`)
- `MOSS_CI_JUDGE_API_KEY` — llm_judge 的 apiKey。两个都配了 F1 才真打分;未配则该 eval 标 error、F1 报 fail(不造假分)

## 已验证

- 13 个测试本地全 pass(quick 9 + full 4,含 C1 自主修 bug 3/3)
- PR 上 CI 跑绿过(docs PR + ci/stable-check-name PR)
- 真实退化演示过(注入 read_file 退化 → CI 报 new_failure → revert)
- 分支保护生效(status check 强制 + up-to-date,过 CI 才能合)

## 已知 follow-up(没做)

- **judge 已真接**:F1 的 llm_judge 现在走 Anthropic `/v1/messages` + Bearer(默认 HORIZON-GLM @ `https://llmapi.horizon.auto`)。本地真 endpoint 验证由用户跑(见下)。CI 上需在 fork Secrets 配 `MOSS_CI_JUDGE_API_URL` + `MOSS_CI_JUDGE_API_KEY`。
- **CI 上 full 层没真跑过**:只本地验证过,CI 上是手动/夜间触发,没实测过 GitHub runner
- **自部署未做**:要搬到自服务器,见 `USAGE.md` 末尾"自定义模型"+ workflow 改 cron/git hook

## 技术要点(踩过的坑)

- **shlex + Windows 路径**:`MOSS_CLI_COMMAND` 含 Windows 反斜杠路径时,CLIBackend 用 `posix=False` 解析(否则 `C:\Users\t` 被吃成 `C:Userst`)
- **prompt 里的 `-m` 会被当 Moss 的 --model flag**:CLIBackend 在 prompt 前插 `--` 分隔(否则 `python -m pytest` → "model=pytest" → HTTP 400)
- **Moss session 解析**:CLIBackend 从 `<cwd>/.moss/sessions/*.jsonl` 提取 tool_use(`{"tool":...,"args":...}`)和 files_modified(write/edit/patch/move 的 path),跑前 snapshot 跑后取差集
- **tests_pass 大小写**:Moss 说 "4 tests pass"(小写 p),不是 pytest 的 "PASSED";评估器不区分大小写匹配 "pass"(别匹配 "ok",会撞 "broken")
- **job name 要稳定**:分支保护按 check 名匹配,job name 不能动态(曾用 `${{ github.event_name }}` 拼接导致匹配不上,改成固定 `Moss capability tests`)
- **AI 测试要答案源隔离**:prompt 不含答案,否则 Moss 能从 prompt 抄(随机 token 才测得住)
