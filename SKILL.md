---
name: resume-intake-workflow
description: 用于固定简历录入流程的专用 skill：当用户发送单份候选人 PDF 简历、发送包含多份 PDF 的 ZIP 批量简历包、或明确要求把简历录入既定飞书多维表格时，使用本 skill。它负责把简历解析为保守的候选人字段，并为既定目标生成受保护的飞书写入计划。适用于这类场景：（1）接收或下载候选人 PDF 简历；（2）接收包含多份 PDF 的 ZIP 并执行批量 intake；（3）从 PDF 中提取文本；（4）把简历内容映射到批准的安全字段集合；（5）为固定目标生成飞书多维表格 create/update payload；（6）把原始 PDF 回填到已创建记录的附件字段；（7）检查某次简历录入写入是否符合业务护栏。若用户明确要求“不要录入，只做分析 / 对比 / 评估”，不要使用本 skill 进入录入链路。这个 skill 是工作流能力，不是 agent 身份定义。不要用于通用 Bitable 探索，也不要在未明确确认前用于创建新的业务目标。
---

# 简历录入工作流

## 概览

这个 skill 只服务于固定的简历录入业务链路：PDF 简历 → 文本提取 → 保守字段抽取 → 受保护写入计划 → 附件回填。

默认路径要尽量收敛，只使用已经批准的目标和安全字段。如果目标、数据表、字段映射存在歧义，先停下来确认，不要猜。

固定目标默认使用 `target_key = resume_intake_v1`，目标真相源是 `references/targets.json`。

这个 skill 应该承载生产规则本身。workspace 级 `AGENTS.md` 只保留很薄的项目定位与入口指引，不要把姓名提取、年龄规则、附件上传参数之类的细节再维护一份到 agent 规则里。

**路径规则：本文件里出现的相对路径，全部相对于当前 skill 目录解析。**
也就是说：
- `scripts/...` 指的是 `skills/resume-intake-workflow/scripts/...`
- `references/...` 指的是 `skills/resume-intake-workflow/references/...`
- **不要**去 workspace 根目录下找同名的 `scripts/`、`docs/`、`references/`

## 输出与沟通规则

- 默认对用户只发送 **1 条最终回复**。
- 执行过程中不要逐步播报，不要一边读文件一边解释，不要每做一步就发一条进度消息。
- 不要向用户暴露内部实现细节，例如 pypdf、pdftotext、临时文件路径、grep 日志、payload 构建过程。
- 只有两种情况可以额外发消息：
  1. 真的卡住，需要用户决策或补信息。
  2. 执行时间明显较长，且确实需要告知“处理中”。即使如此，也只发 **1 条** 简短进度，不要连续发。
- 最终回复保持简洁，优先用 1 到 4 行说明：成功 / 部分成功 / 失败，必要时补一行原因。
- ZIP 批量模式下，优先输出聚合结果，例如“已处理 6 份，成功 5 份，部分成功 1 份”；除非用户要求，不要逐条展开内部细节。
- 不要复述大段流程、规则、字段说明，除非用户明确要求展开。
- 如果用户只问一个窄问题，例如“有没有这个 skill”“读一下 skill”“现在怎么样了”，只回答问题本身，不要擅自进入完整 workflow 解说。

## 快速流程

1. 先确认这是不是简历录入任务，而不是通用的 Bitable 操作。
2. 如果输入是 **单个 PDF**，默认走 **当前 skill 目录下** 的单入口脚本：`scripts/resume_intake_tool_plan.py`。
3. 如果输入是 **单个 ZIP**，并且 ZIP 内含多份 PDF，默认走批量入口：`scripts/batch_resume_intake.py`。
4. ZIP 模式下，先生成 `batch_plan.json`，再只执行其中 `status=planned` 的 job；不要跳过计划层直接手工批量写表。
5. 使用脚本产物里的 `fields.json` / `create_payload.json` / `batch_plan.json` 作为字段与写入参数的真相源，不要临时手工猜字段。
6. **create 阶段必须原样使用生成 payload 里的 `fields` 对象。** 不要把 `联系方式` 擅自拆成 `手机` / `邮箱`，也不要因为主观猜测字段不存在就删除 payload 里已有字段。
7. 只有在飞书工具明确返回字段不存在或类型不匹配，而且你已经先核对过真实 schema 时，才允许调整字段；否则一律按 payload 执行。
8. 实际写入时，使用 OpenClaw 的一等飞书工具，不要直接走 tenant-token OpenAPI。
9. 附件上传必须走多维表格附件模式，也就是 `feishu_drive_file.upload` 时传 `parent_type=bitable_file`，`parent_node=<app_token>`，不要先按普通云盘文件上传。
10. 如果 `应聘者姓名` 缺失，直接停止创建并向用户说明需要人工确认，不允许创建无姓名记录。
11. 除非脚本失败或字段明显缺失，否则不要切换到人工推导模式。

## 护栏

- 除非用户明确要求注册新目标或切换目标，否则只使用固定业务目标。
- 默认 `target_key = resume_intake_v1`，并以 `references/targets.json` 作为目标真相源。
- **不要为这个流程调用 `feishu_bitable_app_table_field.list` 做实时 schema 探索**，固定目标链路直接使用受保护脚本产物。
- 在固定链路里，只允许对批准目标执行记录 `create` 和附件字段 `update`。
- 不要把这个 skill 用于生产链路中的泛化表发现、广义搜索或 schema 探索。
- 姓名来源、payload 使用约束、成功/部分成功判定等业务规则，读取 `references/business-rules.md`。
- ZIP 权限报错、附件归属报错、checkpoint 续跑等批量执行细节，读取 `references/batch-execution.md`。

## 什么时候读什么

- 单个 PDF 默认优先运行 `scripts/resume_intake_tool_plan.py`；单个 ZIP 默认优先运行 `scripts/batch_resume_intake.py`。不要先到处读脚本、列目录、试探流程。
- `feishu_drive_file.upload` 必须使用 `parent_type=bitable_file`、`parent_node=<app_token>`。成功后，立即使用返回的 `file_token` 继续 `scripts/guarded_attachment_update.py` 和后续 update，不要中途改成日志排查模式。
- 手里有 PDF，想提取纯文本时，运行 `scripts/extract_resume_text.py`。
- 手里有简历文本，想生成保守字段 JSON 时，运行 `scripts/build_candidate_fields.py`。
- 需要为批准目标生成校验过的 create/update payload 时，运行 `scripts/guarded_bitable_write.py`。
- 已经拿到 `record_id` 和 `file_token`，想生成附件更新 payload时，运行 `scripts/guarded_attachment_update.py`。
- 只有在排查失败原因时，才读取 `references/business-rules.md` 或 `references/field-mapping.md`。
- ZIP 批量执行细节和 result.json 约定，读取 `references/batch-execution.md`。
- 不要为了“找脚本”去扫描 workspace 根目录；如果本 skill 目录下缺文件，应直接报错并修 skill，而不是换路径乱跑。
- 上述读取和执行默认是内部动作，不需要逐步向用户播报。

## 执行模式

### 1）本地规划

优先使用本地脚本产出稳定工件。

单 PDF 常见工件：
- `resume.txt`
- `fields.json`
- `create_payload.json`
- `tool_plan.json`

ZIP 批量常见工件：
- `batch_plan.json`
- `batch_result.json`
- `jobs/job-xxx/...`

推荐工作目录模式：

```text
runtime/inbound/<message_id>/
```

### 2）实际写入

实际写入使用 OpenClaw 飞书工具：

- `feishu_bitable_app_table_record.create`
- `feishu_drive_file.upload`（附件模式：`parent_type=bitable_file`，`parent_node=app_token`）
- `feishu_bitable_app_table_record.update`

ZIP 批量模式下，先生成 `batch_plan.json`，再按 plan 执行 create / upload / attachment update。

- 完整批量执行顺序、并发建议、checkpoint、result.json、batch_result.json，读取 `references/batch-execution.md`。
- 对用户的批量汇总口径，也以 `references/batch-execution.md` 为准。

### 3）对用户反馈

- 默认只在流程结束后回复一次。
- 如果姓名或年龄因 PDF 字符间距、OCR 断裂而抽取异常，先重跑当前 skill 自带脚本的稳健提取逻辑；只有脚本仍拿不准时，才进入人工确认。
- 除非用户要求详情，否则不要附长表格、长清单、长过程说明。

## 后续扩展说明

如果后面要支持新的 intake 目标、新的安全字段集，或第二条业务流，优先新增独立 reference 或兄弟 skill，不要把这个 skill 膨胀成大而全。这个 skill 只聚焦当前生产简历录入链路和渐进式披露。
