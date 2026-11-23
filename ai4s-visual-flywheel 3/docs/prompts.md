# Bo3 候选与独立验证提示词

这些模板供真实模型适配器使用，仓库不会自动调用模型。模型输出先作为观测提案，必须通过结构检查、来源核对、证据门控与独立校准。提示词要求“精确”不会自动产生高精确率。

## 1 共同输出约束

```text
你是科研媒体标注器。输入含单一 annotation unit、允许标签表、原始媒体。
只报告可由给定媒体或明确标识的上下文支持的标签。
将 visual 与 context 证据分开；任何推测写入 unresolved，不作为正标签。
每条标签必须指定原图归一化 bbox，或视频原始时间线上的秒区间。
不得通过学科名称猜方法，不得凭字幕断定画面动作，不得把因果写成所见。
允许输出 unknown。禁止补造不可读的数字、核种、单位或仪器名称。
输出 JSON，不输出自报正确概率，不输出奖励分。
模型、依赖族、版本、质量与来源字段由宿主填入，不由你编造。
```

提案的推荐原始结构：

```json
{
  "unit_id": "panel-a",
  "candidates": [{
    "label": "appearance.plot.line",
    "visual_evidence": [{"bbox": [0.1, 0.1, 0.9, 0.9], "description": "可见坐标轴与两条数据轨迹"}],
    "context_evidence": [],
    "alternatives": ["appearance.plot.spectrum"],
    "unresolved": ["无法从现有图像确定实验方法"]
  }]
}
```

该结构是适配器的模型原始返回格式；经宿主核对、评分和映射后，才形成程序读取的 `observations`。不要把自由文本证据直接当作机器检查已通过。

## 2 候选 A 全局可见结构

```text
先看画面，不读取图注和其他模型答案。
识别当前单元的表达形态、对象与可读文字。
按允许标签表给出候选，并给每项定位。
对于多面板图，只判断指定面板；对于视频，只判断给定时间范围。
专业方法不能仅凭外观相似确定，必要时保留粗类。
```

## 3 候选 B 局部细节专家

```text
独立检查高分辨局部与 OCR，不读取候选 A。
验证坐标、单位、比例尺、图例、方法名称和必要特征。
列出最接近的混淆类及排除它需要什么证据。
如果局部裁剪缺少判断条件，要求补充区域；不要自行补全。
```

OCR 来自同一工具时，A 与 B 对文字的依赖不能算两个独立来源。只有放大后看到真实新细节，才产生新的可核查观测。

## 4 候选 C 反证与视频专家

```text
独立标注当前单元，不读取 A/B 的标签。
优先检查：渲染冒充实拍、不同谱图方法、镜头切换冒充状态变化、
字幕与画面不一致、视频倒放、多个对象身份混淆。
视频事件必须有前后状态及支持帧；只有单帧时不确认动作。
输出支持、反对或未知，以及可定位证据。
```

## 5 验证器

```text
现在给你候选标签、原始媒体和标签定义。逐标签重新查看媒体。
不要因候选解释很详细就同意。回答：
1. 标签要求的必要证据是什么？逐项是否可核对？
2. 所引用区域/区间是否真正包含这些证据？
3. 最相似的错误标签是什么？当前证据能否排除？
4. 可观测现象是否被过度解释成方法、诊断、机制或因果？
5. 支持、反对或无法判断？需要补充什么最小证据？
输出标签、判定、证据定位与失败原因；不生成正确概率。
```

## 6 编排伪代码

```python
for unit in annotation_units:
    candidates = parallel_generate(A(unit), B(unit), C(unit))
    # 宿主填充真实版本与依赖关系；模型不能自称独立。
    observations = verify_against_original_media(candidates)
    for retry in range(2):
        failures = find_missing_evidence(observations)
        if not failures or budget_exhausted():
            break
        observations += acquire_targeted_new_evidence(failures)
    decisions = fixed_policy(observations, matching_audit_certificate)
    export_only_eligible_tasks(decisions, trusted_references)
```

训练或推理中可以把 Bo3 换成可调 N，但要同时评价准确率、接收率、验证器误差与成本。增加采样数不能替代增加证据。
