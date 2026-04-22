# 简历录入业务规则

## 已批准的生产目标

默认目标 key：

- `resume_intake_v1`

目标注册表真相源：

- `references/targets.json`

## 业务目标

当飞书用户上传 PDF 简历时，默认生产动作是：

1. 在批准的多维表格目标中创建候选人记录
2. 以多维表格附件模式上传原始 PDF（`parent_type=bitable_file`，`parent_node=app_token`）
3. 使用上传后的 file token 回填已创建记录的 `附件` 字段

## 安全写入范围

在固定生产链路中允许：

- `feishu_bitable_app_table_record.create`
- 仅用于附件回填的 `feishu_bitable_app_table_record.update`
- `feishu_drive_file.upload`

在固定生产链路中禁止：

- 通用 app/table 创建
- 根据模糊业务标签推断目标
- 未经明确确认就切换目标
- 在已有用户身份飞书工具可用时，直接走 tenant-token OpenAPI 写入

## 成功判定

- 创建成功 + 附件成功 => 完整成功
- 创建成功 + 附件失败 => 部分成功
- 创建失败 => 失败

补充约束：
- 缺少 `应聘者姓名` 时，必须失败关闭，不允许创建无姓名记录。
- 原始 PDF 是业务必需件，只有“字段成功 + 附件成功”才算完整成功。
- 如果字段成功但附件失败，必须按“部分成功”对外反馈。

## 关键护栏

- 候选人姓名只能来自简历正文、脚本抽取结果或可靠的 PDF 文件名兜底，不能来自消息发送者姓名。
- 不得编造候选人数据；不确定的字段留空。
- 不要手工拼接 create/update payload，优先使用脚本生成的 payload。
- 不要重命名脚本已生成的字段，例如把 `联系方式` 改写成 `手机`、`邮箱` 或其他自造字段。
- 只有在飞书工具明确报字段不存在或类型不匹配，且已完成 schema 核对时，才允许调整字段或删除字段重试。

## 运行顺序

1. 下载或定位 PDF
2. 从 PDF 提取文本
3. 生成保守字段 JSON
4. 生成受保护的 create payload
5. 执行 create
6. 以 `parent_type=bitable_file`、`parent_node=app_token` 上传原始 PDF
7. 生成受保护的附件 update payload
8. 执行 update
9. 汇报结果

## 注册新目标的前置条件

只有在以下条件都满足时，才允许新增目标条目：

- 业务意图明确
- 拿到真实 `app_token`
- 拿到真实 `table_id`
- 已确认这是用于写入路由，不是要新建 app/table

任一条件缺失，都先停下来确认。
