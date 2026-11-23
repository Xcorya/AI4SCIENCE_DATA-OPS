# AI4Science 图像与视频标签体系

这是一套用于数据飞轮的 **0.1 版标签提案**，还没有经过真实数据集的精度验证。目标是让标签可以定位、复查、拒绝和逐版修订。标签数量不代表识别能力，配置中的标签也不代表当前代码已经能从像素识别它们。

机器可读定义见 [`configs/taxonomy.json`](../configs/taxonomy.json)。当前共 106 个标签；稳定英文 ID 用于数据库和模型接口，中文名称用于标注与展示。

## 1. 一条数据同时回答六种问题

| 轴 | 回答的问题 | 示例 | 最低依据 |
| --- | --- | --- | --- |
| `appearance` | 画面采用什么表达方式？ | 折线图、显微图、工程图、网络图 | 当前图像区域的视觉证据；部分类型还须来源信息 |
| `acquisition` | 资产如何采集、测量或生成？ | CT、SEM、XRD、NMR、相机、合成渲染 | 可信元数据、原始文件或一一对应的来源说明 |
| `subject` | 当前内容属于哪个专业语境？ | 材料、化学、力学、分子生物 | 当前面板或镜头自身的对象、量纲、图注或来源证据 |
| `video` | 这一片段是什么视频形式？ | 实验实录、数值仿真、教程、讲座 | 片段证据及必要的来源确认 |
| `event` | 时间上实际看到了什么变化？ | 流动、形变、装配 | 多帧或连续片段证据；检查视角与剪辑 |
| `task` | 可能构造哪种可核验任务？ | 数值读取、计数、时序排序 | 明确问题范围与候选参考；还须经过任务级验证才能入训练集 |

`appearance.plot.line + subject.materials` 是两个不同的命题。“折线图”可能容易确认，“材料学”可能无法确认；只发布有依据的部分标签。`task.value_reading` 表示任务候选，不能直接证明这张图已经有可靠数值真值。

例如，看见灰度纹理不能直接得到 `acquisition.electron_microscopy`；看见彩色云图不能直接得到 `appearance.simulation_field`；看见一个医学影像也不能得到任何疾病诊断。可见外观与来源事实分别取证。

`appearance.photo` 只表示摄影外观，写实生成图或渲染图也可以满足这个标签；它不表示真实实拍。确认相机采集必须另外标注 `acquisition.camera`，并提供已核对的采集元数据或一一对应的可信来源。摄影外观可与 `acquisition.synthetic` 同时成立。这一区分明确标签语义，不构成真实识别精度的验证。

## 2. 标签的作用域

标签落在足够小且证据完整的单位上：`asset → panel/region → shot → track/event_interval`。层级表示定位关系，不表示每个资产必须具备所有单位。

- **图像**：先保存原图；识别多面板并存面板框；对子图、图例、坐标轴或对象框作局部标签。不同面板可以有不同学科和表达形式。
- **视频**：保留解码时间基、切镜边界、有效采样时间；标签可落在镜头、画中画区域、目标轨迹或事件区间。某个片段包含实验，不表示整个视频全为实验。
- **文档页**：`appearance.document_panel` 是容器标签。论文标题不自动传给每张子图，正文也不替代当前子图证据。
- **资产检索标签**：区域标签可汇总成“包含折线图”，必须保存 `derived=true` 和来源单位。汇总标签不是新的独立观察，不能再用来增加票数。

边框采用相对原始解码图像的归一化坐标 `[x_min, y_min, x_max, y_max]`。裁剪、旋转、重采样必须保留坐标变换。时间采用解码展示时间轴的秒数，区间为 `[start, end)`；变帧率视频使用 PTS，不能用假设的固定帧率反推全部时间。

## 3. 层级、多标签与未知

### 3.1 父标签不能提供子标签证据

`appearance.plot` 下有折线、散点、柱状、直方、热力、谱图等子类。确认“这是数据图表”不能证明“这是谱图”。谱图需要可读坐标、单位或可核验图注。`subject.materials` 不能自动展开为 `subject.materials.microstructure`。

子标签通过后，可为检索派生父标签；派生结果应明确来源。实现可以选择只保存原始确认标签，由检索阶段补父标签，避免重复计数。

### 3.2 默认不做全局互斥

一个图可以同时具有 `appearance.plot.line` 和 `appearance.plot.scatter`，例如散点叠加拟合曲线；一个视频可以同时包含实录和动画。106 个标签的 `excludes` 当前均为空，避免错误地把复合内容判为冲突。

需要区分的情形包括：

| 表面上类似 | 应如何处理 |
| --- | --- |
| 柱状图与直方图 | 检查横轴是类别还是连续分箱；不清楚则只给 `appearance.plot` |
| 网络图与分子结构图 | 检查节点/边的化学语义；可为不同区域赋不同标签 |
| CAD 渲染与普通三维渲染 | CAD 要有工程模型、导出记录或明确对应图注；仅有立体外观不够 |
| 实验实录与写实仿真 | 视觉结果可以高度相似，需要来源证明 |
| 自然科学动画与数值仿真 | 动画不保证由方程求解；来源不明时保持粗标签或拒识 |
| 材料微结构与生物细胞 | 不凭相似纹理决定学科，检查当前内容来源 |

若后续需要互斥，应在具体单位、上下文和版本中定义。例如，一个有来源约束的单通道采集记录可被标为 CT 或 MRI，但合成面板可能同时包含二者。不能把元数据层面的规则直接用于整张复合图。

### 3.3 未知不是负样本

标签命题需要分别记录 `supported`、`contradicted`、`insufficient` 等证据状态；最终发布状态再区分确认、待审、拒识、隔离。全流程字段以实际算法接口为准。

没有标 `event.assembly`，不等于“视频不存在装配”。抽查到几帧没有目标，也不等于“整段视频没有目标”。只有明确检查范围与覆盖充分时，才可以生成限定范围内的负标签，例如“在 12.0–15.0 秒这一镜头中未出现可辨认温度计”。

## 4. 视频标签的额外约束

视频内容形式和事件标签分开存储。

- `video.experimental_recording` 是片段形式，仍须来源确认真实采集。
- `event.fluid_flow` 是可见流动，不是自动测得流速或雷诺数。
- `event.state_change_visual` 是可见状态变化，不自动升级为“发生相变”或“发生化学反应”。
- `event.growth_visual` 是可见空间范围增加，不自动证明细胞分裂、晶体生长或某种机制。
- `event.deformation` 要跟踪同一对象，并排除镜头缩放、透视或不同对象切换。

对时序标签至少保留：事件定义、正证据区间、被检查的区间、实际采样时间、缺失时间、目标关联依据、剪辑/遮挡/慢放信息。两个静态帧只有在时间、实体与视角关系可靠时才能支持变化判断。单帧不能证实动作顺序。

“先 A 后 B”还需要事件区间可分。若 A 是 `[1, 4)`、B 是 `[3, 6)`，只能说区间重叠；不能把起始时间先后直接写成“A 完成后 B 开始”。同理，先后顺序不能证明因果。

`requires_temporal=true` 标记时序事件和时序任务。此配置只是最低路由提示；真实视频质量还要检查覆盖、身份、时间和事件关系，不能只检查这个布尔值。

## 5. 专业细类的证据优先级

本提案采用以下取证顺序；冲突必须进入复核：

1. 原始结构/数值/采集文件与可追溯记录。
2. 与当前面板或片段一一对应的可信图注、仪器元数据、作者给出的标注。
3. 可辨认对象、可读单位、图例、通道或结构编码。
4. 仅用于提出候选的视觉相似性或模型先验。

这不是“来源文字一定正确”。来源与像素不匹配、元数据自相矛盾、版本错误时，应保存冲突。多个模型重复读同一图注也不能算多份独立专业证据。

方法轴可以指图背后的测量方法：例如 XRD 曲线同时具有 `appearance.plot` 和 `acquisition.xrd`。SEM/TEM、IR/Raman、NMR/MRI 等相邻方法需要明确来源和精确方法检查；典型外观或谱轴只能辅助核对。不能将峰位置自动升级为晶相、分子身份或疾病真值。

CT、MRI、X 射线和超声都是可用于非医学研究的通用技术，因此不挂在 `acquisition.medical_imaging` 下面。医学成像标签另需对应的医学来源语境，不能由技术名自动派生。

医学和生物标签只做来源确认的领域与成像/结构分类。本标签表没有疾病、临床决策、组织病理诊断结论。将来若增加这些类别，需要单独的专家标注、任务定义与验证集，不能沿用一般视觉标签的门槛。

## 5.1 可执行证据检查声明

每个标签的 `required_checks` 将部分取证要求变成策略引擎可检查的前置条件。72 个标签具有至少一项检查；没有此字段要求也仍需要视觉证据和其他通用门槛。

检查放在支持该标签的每份观察证据内，例如：

```json
{
  "checks": {
    "cad_provenance_confirmed": {
      "passed": true,
      "ref": "source://cad-file-or-export-audit#unit-7"
    }
  }
}
```

这段只是证据对象的局部片段，不是完整 CLI 输入。支持同一标签的每份观察都必须满足该标签的全部 `required_checks`；一个空引用或字符串 `"true"` 不能替代布尔值 `true`。实际执行策略见代码和测试。

检查是可信上游或人工提供的**可追溯声明**。引用存在且声明通过，不证明引用内容真实；当前程序不读取这些来源，不做像素识别，也无法识别伪造声明。实际接入时应由受控验证器填入并审计，不能允许生成候选的模型自行勾选即视为完成验证。

| 检查 ID | 作用 |
| --- | --- |
| `method_metadata_confirmed` | 可信采集/生成元数据或一一对应图注确认了采集方法；不能由视觉相似性或模型自述生成。 |
| `acquisition_context_confirmed` | 与当前区域一一对应的来源确认显微采集语境。 |
| `medical_context_confirmed` | 与当前区域对应的可信来源确认医学成像语境；不包含任何诊断判断。 |
| `cad_provenance_confirmed` | 原生 CAD/工程文件、可追溯导出记录或明确对应来源确认 CAD 语境。 |
| `simulation_provenance_confirmed` | 来源或运行/导出记录确认来自数值模拟；不保证模拟物理正确。 |
| `experiment_provenance_confirmed` | 与当前片段对应的采集链或可信来源确认实验实录；不能仅依靠写实外观。 |
| `local_domain_evidence_confirmed` | 当前面板/镜头自身的对象、单位、图注或原始来源支持该学科标签；父领域/论文标题不够。 |
| `spectrum_axis_confirmed` | 可读坐标、单位或对应原始数据/图注确认谱学编码。 |
| `molecular_context_confirmed` | 结构编码或对应原生分子结构/图注确认分子语义。 |
| `geospatial_context_confirmed` | 地理标记、传感器/平台记录或对应来源确认地理定位语义。 |
| `panel_segmentation_confirmed` | 至少两个独立内容面板已定位；标题/图例不自动视为独立内容面板。 |
| `method_signature_confirmed` | 可信上游核对精确方法 ID、对应来源及适用仪器/谱轴特征；外观或典型坐标单独不够。 |
| `task_reference_available` | 当前候选任务有可复核参考与范围；此检查不等于训练导出许可或任务级正确性证明。 |

原始字段 `evidence_required` 和 `hard_negatives` 中仍有自然语言专业条件；除非被单独编码为验证器，程序不能自动执行它们。策略检查通过不代表所有领域事实均已自动验证。

## 6. 完整标签目录

下表由同目录的 JSON 生成；定义、取证条件和难负例的规范版本以 JSON 为准。

### appearance · 可见表达形态

| ID | 中文名称 | 父标签 | 时序证据 |
| --- | --- | --- | --- |
| `appearance.photo` | 摄影外观 | — | 按证据定义 |
| `appearance.micrograph` | 显微图像 | — | 按证据定义 |
| `appearance.medical_image` | 医学成像图 | — | 按证据定义 |
| `appearance.plot` | 数据图表 | — | 按证据定义 |
| `appearance.plot.line` | 折线图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.scatter` | 散点图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.bar` | 柱状图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.histogram` | 直方图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.heatmap` | 热力图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.spectrum` | 谱图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.image_overlay` | 图像叠加测量 | `appearance.plot` | 按证据定义 |
| `appearance.plot.distribution` | 分布图 | `appearance.plot` | 按证据定义 |
| `appearance.plot.surface_3d` | 三维数据曲面 | `appearance.plot` | 按证据定义 |
| `appearance.diagram` | 科学示意图 | — | 按证据定义 |
| `appearance.diagram.flowchart` | 流程图 | `appearance.diagram` | 按证据定义 |
| `appearance.diagram.apparatus` | 实验装置图 | `appearance.diagram` | 按证据定义 |
| `appearance.diagram.schematic` | 原理或机制示意 | `appearance.diagram` | 按证据定义 |
| `appearance.diagram.circuit` | 电路图 | `appearance.diagram` | 按证据定义 |
| `appearance.network` | 图结构或网络图 | — | 按证据定义 |
| `appearance.molecular_structure` | 分子结构表达 | — | 按证据定义 |
| `appearance.cad_render` | CAD 或工程几何渲染 | — | 按证据定义 |
| `appearance.engineering_drawing` | 工程制图 | — | 按证据定义 |
| `appearance.simulation_field` | 模拟场可视化 | — | 按证据定义 |
| `appearance.map` | 地图或遥感表达 | — | 按证据定义 |
| `appearance.document_panel` | 文档或幻灯片面板 | — | 按证据定义 |
| `appearance.table` | 数据表格 | — | 按证据定义 |
| `appearance.equation` | 数学或符号表达 | — | 按证据定义 |
| `appearance.mixed_panel` | 复合多面板 | — | 按证据定义 |

### acquisition · 采集、测量或生成来源

| ID | 中文名称 | 父标签 | 时序证据 |
| --- | --- | --- | --- |
| `acquisition.optical_microscopy` | 光学显微 | — | 按证据定义 |
| `acquisition.electron_microscopy` | 电子显微 | — | 按证据定义 |
| `acquisition.fluorescence` | 荧光采集 | — | 按证据定义 |
| `acquisition.ct` | CT 采集 | — | 按证据定义 |
| `acquisition.mri` | MRI 采集 | — | 按证据定义 |
| `acquisition.xray` | X 射线采集 | — | 按证据定义 |
| `acquisition.ultrasound` | 超声采集 | — | 按证据定义 |
| `acquisition.remote_sensing` | 遥感采集 | — | 按证据定义 |
| `acquisition.camera` | 相机采集 | — | 按证据定义 |
| `acquisition.synthetic` | 合成或渲染 | — | 按证据定义 |
| `acquisition.scanning_probe` | 扫描探针表征 | — | 按证据定义 |
| `acquisition.afm` | 原子力显微 AFM | `acquisition.scanning_probe` | 按证据定义 |
| `acquisition.sem` | 扫描电子显微 SEM | `acquisition.electron_microscopy` | 按证据定义 |
| `acquisition.tem` | 透射电子显微 TEM | `acquisition.electron_microscopy` | 按证据定义 |
| `acquisition.diffraction` | 衍射表征 | — | 按证据定义 |
| `acquisition.xrd` | X 射线衍射 XRD | `acquisition.diffraction` | 按证据定义 |
| `acquisition.spectroscopy` | 谱学测量 | — | 按证据定义 |
| `acquisition.xps` | X 射线光电子能谱 XPS | `acquisition.spectroscopy` | 按证据定义 |
| `acquisition.nmr` | 核磁共振谱 NMR | `acquisition.spectroscopy` | 按证据定义 |
| `acquisition.ir` | 红外光谱 IR | `acquisition.spectroscopy` | 按证据定义 |
| `acquisition.raman` | 拉曼光谱 Raman | `acquisition.spectroscopy` | 按证据定义 |
| `acquisition.mass_spectrometry` | 质谱 MS | — | 按证据定义 |
| `acquisition.confocal` | 共聚焦显微 | `acquisition.optical_microscopy` | 按证据定义 |
| `acquisition.medical_imaging` | 医学成像采集 | — | 按证据定义 |

### subject · 专业学科

| ID | 中文名称 | 父标签 | 时序证据 |
| --- | --- | --- | --- |
| `subject.physics` | 物理 | — | 按证据定义 |
| `subject.physics.mechanics` | 力学 | `subject.physics` | 按证据定义 |
| `subject.physics.optics` | 光学 | `subject.physics` | 按证据定义 |
| `subject.physics.condensed_matter` | 凝聚态 | `subject.physics` | 按证据定义 |
| `subject.chemistry` | 化学 | — | 按证据定义 |
| `subject.chemistry.reaction` | 化学反应 | `subject.chemistry` | 按证据定义 |
| `subject.chemistry.spectroscopy` | 谱学化学 | `subject.chemistry` | 按证据定义 |
| `subject.materials` | 材料 | — | 按证据定义 |
| `subject.materials.microstructure` | 材料微结构 | `subject.materials` | 按证据定义 |
| `subject.materials.processing` | 材料加工 | `subject.materials` | 按证据定义 |
| `subject.biology` | 生物 | — | 按证据定义 |
| `subject.biology.cell` | 细胞生物 | `subject.biology` | 按证据定义 |
| `subject.biology.molecular` | 分子生物 | `subject.biology` | 按证据定义 |
| `subject.biology.ecology` | 生态 | `subject.biology` | 按证据定义 |
| `subject.medicine` | 医学 | — | 按证据定义 |
| `subject.medicine.imaging` | 医学影像研究 | `subject.medicine` | 按证据定义 |
| `subject.medicine.anatomy` | 解剖结构 | `subject.medicine` | 按证据定义 |
| `subject.earth_space` | 地球与空间 | — | 按证据定义 |
| `subject.earth_space.geoscience` | 地学 | `subject.earth_space` | 按证据定义 |
| `subject.earth_space.climate` | 气候与气象 | `subject.earth_space` | 按证据定义 |
| `subject.earth_space.astronomy` | 天文 | `subject.earth_space` | 按证据定义 |
| `subject.engineering` | 工程 | — | 按证据定义 |
| `subject.engineering.cad` | CAD 与机械设计 | `subject.engineering` | 按证据定义 |
| `subject.engineering.robotics` | 机器人 | `subject.engineering` | 按证据定义 |
| `subject.engineering.electronics` | 电子电气 | `subject.engineering` | 按证据定义 |
| `subject.mathematics_computing` | 数学与计算 | — | 按证据定义 |
| `subject.mathematics_computing.graph` | 图论与网络 | `subject.mathematics_computing` | 按证据定义 |
| `subject.mathematics_computing.numerical` | 数值计算 | `subject.mathematics_computing` | 按证据定义 |

### video · 视频内容形式

| ID | 中文名称 | 父标签 | 时序证据 |
| --- | --- | --- | --- |
| `video.experimental_recording` | 实验实录 | — | 按证据定义 |
| `video.procedure_demo` | 实验或操作教程 | — | 按证据定义 |
| `video.simulation` | 数值仿真视频 | — | 按证据定义 |
| `video.scientific_animation` | 科学动画 | — | 按证据定义 |
| `video.lecture_slides` | 课程或报告视频 | — | 按证据定义 |
| `video.instrument_capture` | 仪器过程录屏 | — | 按证据定义 |
| `video.screen_recording` | 科学软件操作录屏 | — | 按证据定义 |
| `video.mixed` | 混合科学视频 | — | 按证据定义 |

### event · 时序事件

| ID | 中文名称 | 父标签 | 时序证据 |
| --- | --- | --- | --- |
| `event.fluid_flow` | 流动 | — | 必需 |
| `event.deformation` | 形变 | — | 必需 |
| `event.assembly` | 装配或连接 | — | 必需 |
| `event.disassembly` | 拆卸或分离 | — | 必需 |
| `event.state_change_visual` | 可见状态变化 | — | 必需 |
| `event.particle_motion` | 粒子或目标运动 | — | 必需 |
| `event.instrument_operation` | 仪器操作 | — | 必需 |
| `event.growth_visual` | 可见生长或扩展 | — | 必需 |

### task · 下游任务候选

| ID | 中文名称 | 父标签 | 时序证据 |
| --- | --- | --- | --- |
| `task.value_reading` | 数值读取候选 | — | 按证据定义 |
| `task.trend` | 趋势描述候选 | — | 按证据定义 |
| `task.comparison` | 比较候选 | — | 按证据定义 |
| `task.counting` | 计数候选 | — | 按证据定义 |
| `task.structure_reading` | 结构读取候选 | — | 按证据定义 |
| `task.spatial_relation` | 空间关系候选 | — | 按证据定义 |
| `task.temporal_order` | 时序排序候选 | — | 必需 |
| `task.state_tracking` | 状态跟踪候选 | — | 必需 |
| `task.parameter_estimation` | 参数估计候选 | — | 按证据定义 |
| `task.hypothesis_test` | 假设检验候选 | — | 按证据定义 |

## 7. 可扩展性与版本迁移

新增标签应提交：清晰定义、至少一组正例和难负例、所需证据、允许的标注单位、与现有标签的关系、金标集抽样方案及发布策略。近义名称不得另建重复 ID。

- 重命名中文展示文本不更改 ID；改变语义或证据要求必须升版本。
- 拆分一个标签后，旧记录保持旧版本，不强行映射为某个细标签；重新取证后迁移。
- 保存 `taxonomy_version`、策略版本、模型/提示词版本、证据文件哈希及标注时间。
- 用“标签覆盖率、拒识率、各子群精度、标注分歧”评估扩展价值。不能通过删去困难样本掩盖低召回，也不能将粗类精度冒充细类精度。

## 8. 边界

该体系覆盖图像和视频的分类与后续任务路由。CAD 原生几何拓扑、音频、时间序列、点云、代码和实验记录可作为关联资产，但不是通过图像外观直接恢复的真值。识别图中的 CAD 渲染也不代表获得了可执行 CAD 模型。

