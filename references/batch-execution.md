# ZIP 批量执行约定

这份说明只回答一件事：**agent 拿到 ZIP 后，如何把 `batch_plan.json` 真正执行成多份录入结果。**

## 目录

- 适用入口
- 总体原则
- 执行顺序
- 常见故障的优先判断
- 中断后的续跑规则
- 回复用户的建议格式
- 不要做的事

## 适用入口

- 用户发送 **单个 ZIP**
- ZIP 内含多份 PDF 简历
- 默认目标：`resume_intake_v1`（目标注册表见 `references/targets.json`）

## 总体原则

- 飞书会话仍然是串行入口，不要让同一会话的多条消息抢跑。
- 并行的是 **ZIP 内的多个 job**，不是多个用户消息。
- 默认并发度建议 `2` 到 `3`。
- 每个 job 必须独立使用自己的 `tool_plan.json` 和工件目录。
- 对用户默认只发 1 条最终汇总；必要时最多再加 1 条“处理中”。
- **Feishu 写入必须留在原始主会话。不要把 `feishu_bitable_app_table_record.create`、`feishu_drive_file.upload`、`feishu_bitable_app_table_record.update` 放进 subagent / isolated session。**
- 如果要拆子任务提速，子任务只做本地解析、字段抽取、payload 生成、结果校验；主会话负责最终 create / upload / update。

## 执行顺序

### 第 1 步，生成批量计划

运行：

```bash
python3 scripts/batch_resume_intake.py --input-path <zip_or_pdf> --work-dir runtime/inbound/<message_id> --max-workers 3
```

产物：
- `batch_plan.json`
- `jobs/<job_id>/tool_plan.json`
- 每个 job 的中间工件

### 第 2 步，筛出可执行 job

读取 `batch_plan.json`：
- 只执行 `status = planned` 的 item
- `status = failed` 的 item 保留失败信息，最后统一汇总

### 第 3 步，对每个 job 执行完整闭环

对每个 planned job：

> 这一步必须在收到用户消息的主 Feishu 会话里执行，不要切到 subagent。

1. 从 `item.plan.steps[0]` 读取 create 参数
2. 调用：
   - `feishu_bitable_app_table_record.create`
3. 成功后拿到 `record_id`
4. 立刻写 checkpoint：

```bash
python3 scripts/job_checkpoint.py write \
  --job-dir <job_dir> \
  --job-id <job_id> \
  --source-name <source_name> \
  --stage created \
  --record-id <record_id>
```

5. 从 `item.plan.steps[1]` 读取 upload 参数
6. 调用：
   - `feishu_drive_file.upload`
7. 成功后拿到 `file_token`
8. 立刻更新 checkpoint：

```bash
python3 scripts/job_checkpoint.py write \
  --job-dir <job_dir> \
  --job-id <job_id> \
  --source-name <source_name> \
  --stage uploaded \
  --record-id <record_id> \
  --file-token <file_token>
```

9. 运行：

```bash
python3 scripts/guarded_attachment_update.py --target-key <target_key> --record-id <record_id> --file-token <file_token>
```

10. 读取 update payload
11. 调用：
   - `feishu_bitable_app_table_record.update`

### 第 4 步，每个 job 落 result.json

每个 job 完成后，立即写：

```bash
python3 scripts/record_job_result.py \
  --job-dir <job_dir> \
  --job-id <job_id> \
  --source-name <source_name> \
  --status success|partial|failed \
  --record-id <record_id_if_any> \
  --file-token <file_token_if_any> \
  --reason <short_reason>
```

状态规则：
- create 成功 + 附件成功 => `success`
- create 成功 + 附件失败 => `partial`
- create 失败 => `failed`

## 常见故障的优先判断

### 权限类报错

如果 ZIP 批量运行里出现类似以下报错：
- `base:record:create`
- `offline_access`
- `当前应用仅限所有者使用`

先检查是不是错误地把 Feishu 写入放进了 subagent / isolated session，或放进了脱离原始 Feishu 用户授权上下文的子任务。

不要在第一反应里就假定开放平台权限真的缺失。

### 附件归属类报错

如果附件回填报以下类型错误：
- `文件归属校验失败`
- `token 不匹配`
- 类似 bitable 附件归属错误

优先检查是不是误用了普通云盘上传。应改为：
- `parent_type=bitable_file`
- `parent_node=<app_token>`

必要时只重传 upload + attachment update 这一步，不要把问题扩散成整条链路重跑。

## 中断后的续跑规则

- 如果会话中断，但 `jobs/<job_id>/checkpoint.json` 已存在且没有 `result.json`，则该 job 视为**可续跑**。
- `stage=created`：说明记录已创建，续跑时**不要再次 create**，直接从 upload 开始。
- `stage=uploaded`：说明文件已上传，续跑时**不要再次 create/upload**，直接生成附件 update payload 并 update。
- 重新运行 `batch_resume_intake.py` 时，必须复用同一个 `work_dir`，这样它会带出已有 checkpoint/result 状态。

### 第 5 步，生成总汇总

所有 job 完成后，运行：

```bash
python3 scripts/summarize_batch_results.py --work-dir runtime/inbound/<message_id>
```

产物：
- `batch_result.json`

## 回复用户的建议格式

- 默认只发 1 条最终汇总。
- 只有确实耗时较长时，才额外发 1 条简短“处理中”。
- 不要在同一条简历录入会话里连续发送多条过程消息。
- 不要发送“pypdf 未安装”“现在保存文本”“现在执行写入”“附件需要绑定到 bitable，重新上传”这类过程废话。


### 简短汇总

```text
已处理 5 份简历：
- 成功 4 份
- 部分成功 1 份
```

### 如需按文件名列出

```text
已处理 3 份简历：
- 张三.pdf：成功
- 李四.pdf：成功
- 王五.pdf：部分成功（附件失败）
```

## 不要做的事

- 不要多个 job 复用同一个 work_dir
- 不要先 create 完所有记录再统一传附件
- 不要在用户对话里直播每个 job 的中间步骤
- 不要因为一个 job 失败就放弃整个 ZIP，其余 job 继续做
- 不要在 ZIP 模式里临时改字段名或脱离 `tool_plan.json` 手工拼 payload
- 不要让 subagent 直接调用 Feishu 用户态写工具，即使它看起来拿到了完整 job 参数也不行
