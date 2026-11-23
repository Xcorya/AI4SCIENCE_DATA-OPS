# API 与运行说明

从源码目录启动：`python3 -m helix serve --port 8765`。核心无第三方依赖，不建议安装为脱离源码的普通 wheel；Web 与手册从源码目录读取。

默认监听 127.0.0.1，只供本机使用。数据目录默认 `data/`，可用全局参数 `python3 -m helix --data-dir /path COMMAND` 或环境变量 `HELIX_DATA_DIR` 修改。

## HTTP

| 路径 | 方法 | 输入 / 输出 |
| --- | --- | --- |
| `/api/state` | GET | 资产、任务、运行、反馈、真实计数、门槛统计 |
| `/api/session` | GET | 当前本地实例的操作 token |
| `/api/jobs` | GET | 后台作业状态 |
| `/api/demo` | POST | `{}` → 幂等载入原创演示 |
| `/api/run` | POST | `{"limit":24,"provider":"demo"}` → job_id |
| `/api/discover` | POST | `{"connector":"arxiv","query":"...","limit":5}` → job_id |
| `/api/import` | POST | `{"assets":[...]}` → 新增、重复、错误列表 |
| `/api/synthesize` | POST | `{"asset_id":"a_...","kind":"paper","provider":"demo"}` → job_id |
| `/api/feedback` | POST | `{"task_id":"t_...","prediction":"JSON string","model":"name"}` |
| `/api/export?format=rl&split=train&demo=false` | GET | JSONL 下载 |
| `/api/handbook` | GET | 中文手册 Markdown |

POST 使用 `X-Helix-Token`，请求不超过 2 MB。同源页面自动处理 token。它防止网页跨站写入，不是多人身份系统。Host 校验用于限制本地访问；不要绕过这些措施直接挂到公网。

后台任务提交返回 HTTP 202，`job_id` 在 `/api/jobs` 中变为 completed 或 failed。启动失败/参数错误会记录在作业中。当前服务单进程并发一个长任务；CLI 不与服务共享全局任务锁，避免同时对同一目录执行多个构造任务。

资产和任务状态在 SQLite 持久化。数值任务重复运行幂等，非数值草稿每次创建独立版本。网络 API 使用有限重试；模型调用不自动重试，避免不透明地重复计费。

## 导入协议

必需字段：title、source_id、source_url、modality、license、text。

- group_id：来源家族，默认 source_id。派生资产显式共用此字段。
- benchmark：显式封闭基准。已有非基准家族不能被静默改成基准。
- local_file：CLI 专用，相对 Manifest 目录。
- download_url：CLI 配合 `--download`；明确许可、允许主机和大小限制。
- extract：`{"format":"csv","column":"pressure","unit":"Pa"}` 等。
- is_demo：演示声明，默认 false。它不会授权许可，只决定演示过滤与模板模式范围。

文件下载默认允许 arxiv.org、export.arxiv.org、api.crossref.org、zenodo.org。其他公开来源由服务运行者配置 HELIX_DOWNLOAD_HOSTS。不要把未经确认的域名批量加入。

当前近重复判定、内容反病毒、压缩包解压、OCR、PDF 解析、视频抽帧均未自动启用。外部文件按字节保存为对象，不会自动执行。

## 验证数据导出

导出默认排除 demo，拒绝 holdout。RL 数据的 ground_truth 是奖励函数数据列，不能拼入 prompt。SFT 取通过验证的候选；DPO 还需要至少一个未通过候选。

CLI 会同时生成 `.manifest.json`，记录内容哈希和行数。网页下载仅提供 JSONL；正式数据发布建议使用 CLI 生成清单。

## 生产迁移

在公开部署前增加用户认证、权限、持久任务队列、审计、分页、配额和模型成本上限。当前 `/api/state` 返回所有本地记录，适合小规模演示；大数据量应改为分页 API。
