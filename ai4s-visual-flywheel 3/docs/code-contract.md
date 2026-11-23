# 参考实现、输入契约与可验证边界

本仓库的 Python 模块是**离线证据策略引擎**。它消费已有视觉识别结果，执行标签准入、校准、隔离和训练候选导出；没有在后台调用视觉模型、读取真实图片、解码视频或抓取网页。`examples/observations.jsonl` 全部是合成观测，用于演示准入规则，不是准确率评测集。

## 运行

Python 3.10+，直接运行不需要安装第三方包。在仓库根目录：

```bash
python3 scripts/run_demo.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m visual_flywheel run \
  --input examples/observations.jsonl --output-dir work/demo-cli
```

输出为 `decisions.jsonl`、`sft_candidates.jsonl`、`rl_candidates.jsonl`。合成示例没有真实校准证书，训练候选文件为空是预期行为。直接运行脚本时，`work/demo/summary.json` 同时记录状态统计。

0.1.1 起，`python3 -m pip install .` 安装的命令可以在仓库目录外运行，使用 wheel 内默认配置。源码运行读取仓库 `configs/`。`--policy`、`--taxonomy` 仍可显式覆盖。证书指纹增加策略引擎版本；改变接收、校准或奖励语义时须更新该版本，使旧证书失效。

## 一行代表一个标注单元

每行 JSON 是同一素材中的**一个 panel、对象区域或视频片段**。`asset_id` 表示素材，`unit_id` 表示这个标注单元；所有 observation 必须具有相同 `unit_id`。不同 panel 或不同事件的投票不能合并到同一行。程序检查 ID 匹配，实际裁剪和坐标是否对应这个单元仍由上游负责。

```json
{
  "asset_id": "demo-image-001",
  "unit_id": "panel-a",
  "synthetic": true,
  "modality": "image",
  "cohort": "synthetic_demo_v1",
  "split": "train",
  "quality": {"usable": true, "audit_ref": "synthetic://quality"},
  "source": {
    "url": "https://example.invalid/demo-image-001",
    "source_group": "demo-paper-001",
    "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "rights": {
      "status": "cleared",
      "training_allowed": true,
      "redistribution_allowed": true,
      "license_id": "CC0-1.0",
      "audit_ref": "synthetic://rights-audit"
    }
  },
  "observations": [
    {
      "label": "appearance.plot.line",
      "unit_id": "panel-a",
      "observer_id": "visual-model-a",
      "dependency_family": "model-a-evidence-a",
      "verdict": "support",
      "score": 0.99,
      "evidence": {
        "channel": "visual",
        "ref": "synthetic://crop-a",
        "bbox": [0.1, 0.1, 0.9, 0.9]
      }
    }
  ]
}
```

上例只有一个证据依赖家族，不能通过准入。`synthetic: true` 的观测永远不导出为训练候选。

JSON 对象、数组、ID 与来源字段会进行类型检查。畸形记录进入复核或隔离，不应让同批其他记录崩溃；`synthetic` 如提供必须是布尔值，不能写成字符串 `"false"`。策略阈值、最少家族数与标签层级配置错误会明确终止本次运行。JSON 语法错误或 `NaN`、`Infinity` 等非标准常量会给出文件与行号，命令退出码为 2，不产生本次训练导出。

| 字段 | 实现语义 |
| --- | --- |
| `modality` | 仅 `image` 或 `video`。 |
| `split` | `train`、`validation`、`test`、`tune` 或 `audit`；仅 train 可导出训练候选。 |
| `cohort` | 固定的数据总体，例如某来源集合、学科、采样时间范围与标注粒度；视频 segment 与 whole_asset 必须使用不同 cohort，证书必须精确匹配。 |
| `quality` | 上游质量检测的明确通过记录。缺失、失败或缺少审计引用进入人工复核。 |
| `source_group` | 同一论文、实验、视频母片等相关素材必须归组；同组不能跨切分。 |
| `sha256` | 源素材字节哈希的十六进制值；批处理中检查精确副本跨切分。 |
| `rights` | 上游完成的授权审计声明。程序检查声明字段，不判断许可证条款。 |
| `score` | 上游排序分值，范围 `[0,1]`；不是经过验证的正确概率。 |
| `dependency_family` | 证据依赖的归组；同一模型 Bo3、多次提示、复制 OCR/字幕证据不能冒充不同家族。 |
| `verdict` | `support` 或 `contradict`。有有效定位的高分反证阻止准入。 |
| `bbox` | 相对原图的归一化 `[x1,y1,x2,y2]`，边界必须有效且有正面积。 |

依赖家族归组是可信上游注册表的职责。相同 OCR 片段、字幕、图注或其他同一事实来源经多个模型转述时，须在注册表中合并为同一依赖家族。程序只按所给家族 ID 去重；不同 ID 不构成统计独立性的证明，也没有自动构建证据依赖图。

## 细标签证据检查

`configs/taxonomy.json` 中的 `required_checks` 是机器可执行的必需检查集合。例如 CAD 渲染必须提供 `cad_provenance_confirmed`，精细采集方法需要相应方法元数据与特征验证。**每一个用于支持该标签的有效 observation** 都必须带齐检查：

```json
{
  "channel": "visual",
  "ref": "source://visual-crop",
  "bbox": [0.1, 0.1, 0.9, 0.9],
  "checks": {
    "cad_provenance_confirmed": {
      "passed": true,
      "ref": "source://audited-cad-export-metadata"
    }
  }
}
```

程序核对检查 ID、`passed: true` 和非空来源引用；不会替代真实元数据比对、工具验证或专家判断。单纯添加字符串不能证明科学真值。父标签的支持不自动产生任何细标签。细标签必须单独提交自己的直接观测和所有必需检查。未观测到的标签保持未知，不自动作为负标签。

必需的正向方法检查仅约束 `support`。`contradict` 观测仍必须有合法视觉定位与相应时间证据，但不需要证明被反驳标签的正向方法签名。例如已定位的 TEM 反例不应因为无法提供 SEM 的正向签名而被丢弃。

## 视频证据

视频记录增加正的有限数 `duration_seconds`，并设置 `claim_scope`：局部存在性标签使用 `segment`；整段断言使用 `whole_asset`。省略时默认为 `segment`；其他值或拼写错误进入人工复核，不能跳过覆盖检查。后者需要真实检查窗口覆盖达到策略阈值。

```json
{
  "channel": "visual",
  "ref": "source://clip-and-tracks",
  "interval": [2.0, 10.0],
  "observed_times": [2.0, 6.0, 10.0],
  "observed_segments": [[2.0, 4.0], [8.0, 10.0]],
  "time_order_verified": true,
  "relations": [
    {"before": [2.0, 4.0], "after": [8.0, 10.0]}
  ]
}
```

`interval` 是标签声称发生的区间，不能当成已检查覆盖范围。`observed_segments` 必须代表上游确实连续检查的窗口；程序计算窗口并集，避免重复计数。两个稀疏关键帧不代表看过两帧之间的全部视频。

局部存在性与整段断言不是同一审计总体；生产 cohort 注册表必须把 `claim_scope`、标注单元尺度及抽样方式纳入固定总体定义，例如 `materials-video-v1__segment` 与 `materials-video-v1__whole_asset`。当前代码只比较所声明的 cohort 字符串，不能核验这个注册表含义；不得复用同一 cohort 为两种粒度签发证书。

对于 `requires_temporal: true` 的标签，必须有至少两个唯一、升序、处于声明区间内的 `observed_times`，且 `time_order_verified` 明确通过。给出的 before/after 关系还必须时间有序、位于声明区间内。程序验证结构与边界，不凭这些声明确认运动、因果或实验真实发生。

## 分值与状态

一个依赖家族内先取支持分值的最小值，避免在同家族 Bo3 中挑最高置信度；家族间排序后取第 `minimum_independent_families` 个分值作为候选分值。默认要求至少两个家族。该保守聚合仍需在固定总体上校准，不能被称为正确概率。

| 状态 | 含义 |
| --- | --- |
| `quarantine` | 授权未明确通过，或同批输入发现 source_group/精确副本跨切分。 |
| `human_review` | 质量、定位、依赖家族、必需检查、时间关系、覆盖、矛盾或阈值检查未通过。 |
| `provisional` | 结构与证据支持达到候选条件，但没有匹配的有效精度证书。 |
| `accepted` | 通过所有硬门控，且分值达到匹配证书的阈值。 |
| `abstain` | 没有候选标签。 |

每个标签都有独立状态。记录存在复核项时仍可保留其他已准入标签作为**局部正标签**；导出不会把未列出的标签当成不存在。

## 校准：调阈值与审计分离

`policy.pipeline_version` 必须固定记录模型/权重、提示、预处理、抽帧、跟踪及证据工具的注册表版本。参考默认值 `unconfigured-reference-v1` 表示尚未接入真实识别系统。生产系统须替换为真实不可变版本。整个 policy 和 taxonomy 参与 SHA-256 指纹；任意改动后旧证书失效。

每个 calibration JSONL 行代表固定上游管线和本策略硬门控通过后的一个标签候选，格式如下：

```json
{
  "label": "appearance.plot.line",
  "modality": "image",
  "score": 0.96,
  "correct": true,
  "split": "audit",
  "source_group": "external-audit-paper-001",
  "content_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "cohort": "audited-source-cohort-v1",
  "policy_fingerprint": "sha256-from-visual_flywheel.policy.fingerprint",
  "hard_gate_eligible": true,
  "reference_id": "external-adjudicated-gold-001",
  "synthetic": false
}
```

上例哈希仅用于展示格式，真实输入必须替换为原始资产字节的 SHA-256。程序要求 64 位十六进制并统一大小写；给同一文件改 source group 或把哈希改为大写，不能增加独立审计数量。

`score` 必须由**实际同一固定策略**算出，`correct` 必须来自外部专家裁决或可执行真值。判断正确应同时覆盖标注单元、标签层级与科学含义，不能只核对答案字符串。人工抽样须独立于待评模型，按 source group 随机抽取候选；每个 `(label, modality, source_group)` 只计一个独立单位，同一 `(label, modality, content_sha256)` 也只能出现一次。程序拒绝重复计数和 tune/audit 同组或精确副本泄漏，不实现人工抽样或审计身份核验。

```bash
PYTHONPATH=src python3 -m visual_flywheel calibrate \
  --input work/external_gold.jsonl --output work/calibration.json \
  --trusted-references

PYTHONPATH=src python3 -m visual_flywheel run \
  --input work/real_observations.jsonl --calibration work/calibration.json \
  --output-dir work/real_decisions
```

`--trusted-references` 是操作方“已核验外部参考来源”的声明，不是本程序实施了身份或科学真实性核验。证书是**本地可信生产者产生的工件**，没有密码学签名；不要载入外部不可信证书。加载时会核对 policy/taxonomy 指纹、cohort、合成标记、统计计数及重新计算的置信下界，但不证明审计记录真实。

每个 `(label, modality)` 在 tune 集上选择阈值，再在独立 audit 集上计算通过阈值样本的单侧精确 Clopper–Pearson 精度下界。对本次尝试的全部标签组合使用 Bonferroni 分配 `alpha / m`，包括没有认证成功的组合。只有下界达到目标、审计组数达到最低要求、参考来源声明已核验且数据非合成时才认证。

该下界依赖外部金标正确、source group 足够独立以及部署总体与审计总体可交换。分布变化、漏归组、重复尝试直到通过、或直接在 audit 集上调模型都会破坏解释。`minimum_audit_n: 100` 只是最低规模，并不意味着 100 个全对就能证明 98% 精度。少量样本无法达到下界时保持拒识或补充独立审计；本实现没有逐次试验的统计控制。

## SFT / RL 导出与奖励

只从 `train` 切分导出，合成样本和隔离记录不导出。SFT 输出为 `calibrated_pseudo_labels_partial_not_exhaustive`，保留素材来源、证据、版本和指纹；这是一种机器伪标签监督，不是人工全量标注。

RL 还要求 `reference_reviews` 中存在外部参考裁决：

```json
{
  "label": "appearance.plot.line",
  "unit_id": "panel-a",
  "status": "verified",
  "method": "human",
  "reviewer_id": "external-reviewer-id",
  "reference_id": "external-gold-id",
  "question": "识别左侧坐标面板的图表类型，并给出该面板的位置。",
  "bbox": [0.1, 0.1, 0.9, 0.9]
}
```

`method` 仅接受 `human` 或 `executable_oracle`。视频参考使用 `interval`；环境参考的 `duration_seconds` 从素材记录取值，审阅记录若也声明时长则必须与素材一致。任务问题也需外部审核，避免答案泄漏或歧义。奖励要求标签完全匹配，并且相对于独立参考的框 IoU 或时间 IoU 至少 0.5；错误标签即使框重合也得零分。预测时间须满足 `0 <= start < end <= duration_seconds`；参考缺少标签或有效定位、视频缺少合法时长、预测含额外字段或越界时均返回零分。当前二元奖励仅实现标签定位这一类任务，不覆盖科学推理正确性、数值问题、因果问题或完整 RL 训练。

```bash
PYTHONPATH=src python3 -m visual_flywheel reward \
  --response work/response.json --reference work/reference.json
```

训练框架只能把 `media`、`prompt`、候选词表作为模型输入；`reference`、来源审计和审阅者字段保留在环境端。不要把参考答案直接拼进模型提示。导出结果是训练**候选工件**，尚需真实媒体装载、任务适配与训练器接入。

## 尚未实现的生产部件

真实模型推理、页面抓取、帧提取、OCR、跟踪、质量测量、签名审计、近重复检索、跨批次泄漏注册表、人工审阅系统及训练作业均属于接入层。当前跨切分检查只覆盖同一次 `classify_batch` 输入中的 source group 和字节哈希；不检测语义近重复，不记忆历史批次。生产系统应先将整个数据清单及历史评测保留集加载到持久化隔离与切分注册表，再调用本策略。
