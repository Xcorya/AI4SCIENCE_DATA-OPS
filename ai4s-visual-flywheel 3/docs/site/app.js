"use strict";

// All fixtures below are hand-authored synthetic illustrations. No model runs here.
const taxonomy = [
  { id: "appearance.plot.line", axis: "appearance", axisName: "内容形态", name: "折线图", evidence: "存在坐标轴、连续线段与序列映射；可用结构解析器复核。", boundary: "不能仅凭一条曲线断言实验结论或因果关系。" },
  { id: "appearance.plot.scatter", axis: "appearance", axisName: "内容形态", name: "散点图", evidence: "坐标系内离散标记点与图例关系；区分图像颗粒。", boundary: "点状纹理可能来自显微图，需确认坐标映射。" },
  { id: "appearance.micrograph", axis: "appearance", axisName: "内容形态", name: "显微成像", evidence: "微观纹理、标尺与仪器元数据相互支持。", boundary: "相似纹理不能直接确定 TEM、SEM、细胞类型或疾病。" },
  { id: "appearance.cad_render", axis: "appearance", axisName: "内容形态", name: "CAD 渲染图", evidence: "可核对的 CAD 来源、几何视图或模型元数据。", boundary: "仅看到工业零件，不能判定 CAD 文件存在或结构可制造。" },
  { id: "appearance.network", axis: "appearance", axisName: "内容形态", name: "网络 / 关系图", evidence: "可辨识节点、边、图例与关系语义。", boundary: "节点图不能自动归为分子图、因果图或真实拓扑。" },
  { id: "appearance.mixed_panel", axis: "appearance", axisName: "内容形态", name: "多面板科学图", evidence: "版面分割、子图边界、面板编号与局部内容定位。", boundary: "对子图分别打标签；不能用某一子图标签覆盖全图。" },
  { id: "acquisition.electron_microscopy", axis: "acquisition", axisName: "采集来源", name: "电子显微", evidence: "可核验的仪器记录或原始图注与当前图像对应。", boundary: "不单凭灰度、纹理或放大倍数猜测 SEM / TEM。" },
  { id: "acquisition.tem", axis: "acquisition", axisName: "采集来源", name: "TEM 采集", evidence: "可核验的采集元数据与方法特征相互确认。", boundary: "仅显微外观不能区分 TEM / SEM；需通过两个方法检查。" },
  { id: "subject.materials", axis: "subject", axisName: "学科", name: "材料科学", evidence: "可定位的标题、图注、样品说明与来源元数据。", boundary: "显微成像是跨学科方法，外观本身不足以确定学科。" },
  { id: "subject.chemistry", axis: "subject", axisName: "学科", name: "化学", evidence: "化学实体、反应记录、来源说明与局部媒体对应。", boundary: "实验器皿、颜色变化不等于特定反应已发生。" },
  { id: "subject.earth_space.geoscience", axis: "subject", axisName: "学科", name: "地球科学", evidence: "地理范围、传感器与地图坐标等上下文可验证。", boundary: "自然风景与遥感图不能只靠外观混为同一类。" },
  { id: "video.experimental_recording", axis: "video", axisName: "视频形式", name: "实验实录", evidence: "实验来源、连续过程与媒体的局部对应。", boundary: "有器皿的动画不能自动归为实验实录。" },
  { id: "video.procedure_demo", axis: "video", axisName: "视频形式", name: "操作教程", evidence: "教程意图、可观察操作与步骤说明。", boundary: "旁白描述的动作不等于画面已经执行。" },
  { id: "event.fluid_flow", axis: "event", axisName: "时间事件", name: "流动（局部动作：混合）", evidence: "起止时间、相邻帧变化与动作参与物的一致证据。", boundary: "单帧器皿不能证明混合动作；不能由混合推断反应。" },
  { id: "event.state_change_visual", axis: "event", axisName: "时间事件", name: "可见状态变化", evidence: "跨时间窗观察到可见状态变化，必要时配合仪器记录。", boundary: "镜头切换、光照变化和动画效果不构成物理相变证据。" },
  { id: "event.instrument_operation", axis: "event", axisName: "时间事件", name: "仪器操作", evidence: "步骤边界、操作顺序、器材与任务说明。", boundary: "未覆盖的时间段不自动标成背景，不能推断缺失步骤。" },
  { id: "task.value_reading", axis: "task", axisName: "任务", name: "数值读取候选", evidence: "可复核的轴、图例、数据点或表格重建目标。", boundary: "OCR 无法辨认时不生成精确数值答案。" },
  { id: "task.state_tracking", axis: "task", axisName: "任务", name: "状态跟踪候选", evidence: "标注过的时间区间与边界容差，使用 tIoU 等指标验证。", boundary: "评价集按源视频分组，避免同一视频片段跨集合。" },
  { id: "task.structure_reading", axis: "task", axisName: "任务", name: "结构读取候选", evidence: "标签与区域坐标、OCR span、时间窗之间的显式对应。", boundary: "有框不等于有证据；还需检验框内内容支持该标签。" },
];

const fixtures = [
  {
    id: "SYN-IMG-001", mode: "image", title: "双序列科学折线图", kind: "CHART / REGION", note: "多源支持 · 尚未校准", visual: "chart", rights: "redistributable", temporal: null,
    description: "合成折线图含两条序列和坐标轴。形态证据充分；图像本身不能支持任何专业学科结论。",
    candidates: [
      { name: "坐标与连续线条优先", labels: ["appearance.plot.line", "task.value_reading"], explanation: "提取坐标系、图例与两条连续线；暂不判断学科。" },
      { name: "领域上下文假设", labels: ["appearance.plot.line", "subject.materials"], explanation: "尝试材料学归类，但当前没有可对应的图注证据。" },
      { name: "局部标记点假设", labels: ["appearance.plot.scatter"], explanation: "把曲线上的点视为散点；需要检查连续线段。" },
    ],
    labels: ["appearance.plot.line", "task.value_reading", "subject.materials"],
    evidence: [
      { id: "E1", family: "vision-family-A", label: "appearance.plot.line", quality: .93, support: true, title: "视觉结构：连续线条与共同坐标轴", location: "bbox [0.12, 0.10, 0.88, 0.85]", detail: "候选生成器的三次输出合并为同一依赖组。" },
      { id: "E2", family: "chart-parser-B", label: "appearance.plot.line", quality: .91, support: true, title: "结构解析：两条连续序列", location: "series_count=2; axis_count=2", detail: "不同解析路径支持可见形态；仍需真实金标测量误差。" },
      { id: "E3", family: "chart-parser-B", label: "task.value_reading", quality: .9, support: true, title: "图表对象与轴范围可解析", location: "axis x: 0–5; axis y: 0–100", detail: "只支持结构读取，不生成未绘制的精确实验值。" },
      { id: "E4", family: "ocr-family-C", label: "task.value_reading", quality: .88, support: true, title: "文字通道：轴标签与图例可读", location: "OCR spans: Step / Response / A / B", detail: "该 OCR 结果未作为视觉生成器的上游输入。" },
    ],
    target: { label_ids: ["appearance.plot.line"], evidence_ids: ["E1", "E2"], answer_scope: "visible_representation" },
  },
  {
    id: "SYN-IMG-002", mode: "image", title: "显微纹理还是模拟纹理？", kind: "MICROSCOPY / AMBIGUOUS", note: "相关候选 · 等待外部证据", visual: "micro", rights: "redistributable", temporal: null,
    description: "合成颗粒纹理缺少标尺和仪器记录。多份显微候选共享模型依赖，另有模拟图假设；重复判断不能被当成独立支持。",
    candidates: [
      { name: "TEM 外观假设", labels: ["appearance.micrograph"], explanation: "从纹理推断显微成像；缺少仪器来源证据。" },
      { name: "TEM 复述假设", labels: ["appearance.micrograph", "subject.materials"], explanation: "重复同一视觉判断，并添加未支持的学科猜测。" },
      { name: "模拟图替代假设", labels: ["appearance.simulation_field"], explanation: "相近纹理也可能来自模拟输出，形成待解歧义。" },
    ],
    labels: ["appearance.micrograph", "subject.materials"],
    evidence: [
      { id: "E1", family: "vision-family-A", label: "appearance.micrograph", quality: .91, support: true, title: "候选 A：颗粒状显微外观", location: "full image", detail: "同一视觉模型采样，不能确定具体成像技术。" },
      { id: "E2", family: "vision-family-A", label: "appearance.micrograph", quality: .92, support: true, title: "候选 B：相同外观复述", location: "full image", detail: "与 E1 共用依赖组，不增加证据组数量。" },
      { id: "E3", family: "vision-family-A", label: "appearance.micrograph", quality: .9, support: true, title: "候选 C：重复提示变体", location: "full image", detail: "即使质量分更高，也不能伪装为外部复核。" },
    ], target: null,
  },
  {
    id: "SYN-IMG-003", mode: "image", title: "零件渲染图的来源待确认", kind: "CAD / RIGHTS UNKNOWN", note: "权利待确认 · 隔离", visual: "cad", rights: "unknown", temporal: null,
    description: "合成示例模拟来源不明的零件图。即使视觉与几何元数据支持 CAD 渲染，未确认的再分发权利也会阻止进入公开数据集。",
    candidates: [
      { name: "CAD 形态假设", labels: ["appearance.cad_render"], explanation: "存在几何渲染与视图特征。" },
      { name: "机械学科假设", labels: ["appearance.cad_render", "subject.physics.mechanics"], explanation: "学科还需可核对的来源说明。" },
      { name: "实拍替代假设", labels: ["appearance.photo"], explanation: "材质外观也可能来自实体照片。" },
    ],
    labels: ["appearance.cad_render"],
    evidence: [
      { id: "E1", family: "vision-family-A", label: "appearance.cad_render", quality: .94, support: true, title: "轮廓与渲染特征", location: "full image", detail: "合成视觉支持，不等于证实实际可制造性。" },
      { id: "E2", family: "geometry-metadata-B", label: "appearance.cad_render", quality: .95, support: true, title: "几何来源元数据", location: "source_kind=cad_render", detail: "元数据可支持标签，但许可证字段仍为 unknown。" },
    ], target: null,
  },
  {
    id: "SYN-VID-001", mode: "video", title: "混合动作的时间窗", kind: "EXPERIMENT / EVENT", note: "局部事件支持 · 未校准", visual: "mixing", rights: "redistributable", temporal: { duration: 12, start: 3, end: 9, inspected: [[0, 12]], ordered: true, scope: "event_only" },
    description: "合成 12 秒视频示意：仅 [3, 9] 秒有搅拌动作。目标是动作与时间定位，不推断化学反应，也不把画面外阶段补全。",
    candidates: [
      { name: "可见动作假设", labels: ["event.fluid_flow", "task.state_tracking"], explanation: "将可见搅拌动作定位到局部时间窗。" },
      { name: "反应推断假设", labels: ["subject.chemistry.reaction", "subject.chemistry"], explanation: "器皿与颜色不足以支持特定反应，送入反证检查。" },
      { name: "静态器材假设", labels: ["appearance.photo"], explanation: "只描述实验场景，遗漏了时间事件。" },
    ],
    labels: ["event.fluid_flow", "task.state_tracking", "subject.chemistry"],
    evidence: [
      { id: "E1", family: "video-family-A", label: "event.fluid_flow", quality: .92, support: true, title: "视频通道：连续旋转动作", location: "t=[3.0, 9.0] seconds", detail: "相邻帧中工具与液体运动一致。" },
      { id: "E2", family: "motion-parser-B", label: "event.fluid_flow", quality: .9, support: true, title: "运动路径：局部循环运动", location: "t=[3.2, 8.8] seconds", detail: "独立运动路径支持动作，但不证明化学变化。" },
      { id: "E3", family: "video-family-A", label: "task.state_tracking", quality: .92, support: true, title: "事件起止边界候选", location: "start=3.0; end=9.0", detail: "可转化为时间区间预测任务。" },
      { id: "E4", family: "motion-parser-B", label: "task.state_tracking", quality: .89, support: true, title: "边界复核", location: "boundary tolerance=0.5 seconds", detail: "演示容差；真实容差需写入标注协议。" },
    ], target: { event_id: "event.fluid_flow", interval_seconds: [3, 9], reward_kind: "temporal_iou", boundary_tolerance_seconds: .5 },
  },
  {
    id: "SYN-VID-002", mode: "video", title: "稀疏抽帧不能代表全片", kind: "PROCEDURE / COVERAGE GAP", note: "覆盖不足 · 人工复核", visual: "sparse", rights: "redistributable", temporal: { duration: 120, start: 0, end: 120, inspected: [[0, 4], [56, 60], [116, 120]], ordered: true, scope: "whole_video" },
    description: "合成 120 秒视频只检查了三个短时间窗。看见开头与结尾不能证明完整操作顺序，未检查的 108 秒保持 unknown。",
    candidates: [
      { name: "全流程假设", labels: ["event.instrument_operation"], explanation: "根据少数帧拼接全流程，存在未观察的时间缺口。" },
      { name: "已观察窗口假设", labels: ["appearance.photo"], explanation: "仅对已检查片段描述局部场景。" },
      { name: "顺序推断假设", labels: ["task.state_tracking"], explanation: "不能从稀疏抽帧确认全部步骤与边界。" },
    ],
    labels: ["event.instrument_operation", "task.state_tracking"],
    evidence: [
      { id: "E1", family: "video-family-A", label: "event.instrument_operation", quality: .94, support: true, title: "已观察窗口出现操作动作", location: "t=[0,4], [56,60], [116,120]", detail: "局部支持不能扩展为完整视频的步骤覆盖。" },
      { id: "E2", family: "asr-transcript-B", label: "event.instrument_operation", quality: .9, support: true, title: "字幕提到操作步骤", location: "t=[58,60] seconds", detail: "字幕可能预告或回顾；需与画面时间对齐。" },
      { id: "E3", family: "video-family-A", label: "task.state_tracking", quality: .92, support: true, title: "候选步骤边界", location: "full-video claim", detail: "当前无法覆盖或验证全部边界。" },
      { id: "E4", family: "asr-transcript-B", label: "task.state_tracking", quality: .88, support: true, title: "语言时间提示", location: "full-video claim", detail: "未观察区域不能自动当作负例。" },
    ], target: null,
  },
];

let mode = "image";
let current = fixtures[0];
let selectedAxis = "all";
let activePanel = "candidates";
const $ = (selector) => document.querySelector(selector);
const labelName = (id) => taxonomy.find((item) => item.id === id)?.name || ({ "subject.physics.mechanics": "机械 / 力学", "appearance.photo": "实拍图像", "appearance.simulation_field": "模拟场图", "subject.chemistry.reaction": "化学反应" }[id]) || id;
const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const requiredChecks = {
  "appearance.micrograph": ["acquisition_context_confirmed"],
  "appearance.cad_render": ["cad_provenance_confirmed"],
  "subject.materials": ["local_domain_evidence_confirmed"],
  "subject.chemistry": ["local_domain_evidence_confirmed"],
  "task.value_reading": ["task_reference_available"],
  "task.structure_reading": ["task_reference_available"],
  "task.state_tracking": ["task_reference_available"],
};
const fixtureChecks = {
  "SYN-IMG-001": { task_reference_available: true },
  "SYN-IMG-002": {},
  "SYN-IMG-003": { cad_provenance_confirmed: true },
  "SYN-VID-001": { task_reference_available: true },
  "SYN-VID-002": {},
};

function intervalCoverage(intervals, duration) {
  if (!Number.isFinite(duration) || duration <= 0 || !Array.isArray(intervals)) return null;
  if (intervals.some((span) => !Array.isArray(span) || span.length !== 2 || !span.every(Number.isFinite) || span[0] < 0 || span[0] >= span[1] || span[1] > duration)) return null;
  const ordered = intervals.map((span) => [...span]).sort((a, b) => a[0] - b[0]);
  let total = 0, start = 0, end = 0;
  for (const [a, b] of ordered) {
    if (a > end) { total += end - start; start = a; }
    end = Math.max(end, b);
  }
  return (total + end - start) / duration;
}

function assess(sample) {
  const minFamilies = Number($("#family-threshold").value);
  const minQuality = Number($("#quality-threshold").value);
  const wholeVideoMinCoverage = .95;
  const temporalBlocks = [];
  let coverage = null;
  if (sample.temporal) {
    const t = sample.temporal;
    coverage = intervalCoverage(t.inspected, t.duration);
    if (coverage === null || !Number.isFinite(t.start) || !Number.isFinite(t.end) || t.start < 0 || t.start >= t.end || t.end > t.duration) temporalBlocks.push("时间区间或检查窗口无效。");
    if (t.scope === "whole_video" && coverage !== null && coverage < wholeVideoMinCoverage) temporalBlocks.push(`全片主张仅检查 ${(coverage * 100).toFixed(0)}% 时长，不能覆盖全片。`);
    if (t.ordered !== true) temporalBlocks.push("时间顺序尚未核准，需要复查媒体与边界。");
  }
  const decisions = sample.labels.map((id) => {
    const usable = sample.evidence.filter((e) => e.label === id && e.support && e.quality >= minQuality);
    const families = [...new Set(usable.map((e) => e.family))];
    const contradicted = sample.evidence.some((e) => e.label === id && !e.support && e.quality >= minQuality);
    const missingChecks = (requiredChecks[id] || []).filter((check) => !fixtureChecks[sample.id]?.[check]);
    const blockReasons = [...temporalBlocks];
    if (families.length < minFamilies) blockReasons.push("证据依赖组不足。");
    if (contradicted) blockReasons.push("存在有效反证。");
    if (missingChecks.length) blockReasons.push("缺少必要上下文检查。");
    return { label_id: id, state: blockReasons.length === 0 ? "provisional" : "review", supporting_family_count: families.length, family_ids: families, evidence_ids: usable.map((e) => e.id), missing_checks: missingChecks, contradiction: contradicted, block_reasons: blockReasons };
  });
  const reasons = [];
  let status = "provisional";
  if (sample.rights !== "redistributable") { status = "quarantine"; reasons.push("来源权利未确认，禁止公开数据导出。"); }
  if (temporalBlocks.length) { if (status !== "quarantine") status = "review"; reasons.push(...temporalBlocks); }
  const supported = decisions.filter((d) => d.state === "provisional");
  if (supported.length === 0) { if (status !== "quarantine") status = "review"; reasons.push("没有标签获得足够证据依赖组支持。"); }
  if (supported.length > 0) reasons.push(`${supported.length} 个标签通过当前演示规则；其余标签保留复核。`);
  reasons.push("缺少独立人工金标校准：输出保持 provisional。");
  return { sample_id: sample.id, status, release_allowed: false, calibration_status: "not_calibrated", inspected_coverage: coverage, thresholds: { min_families: minFamilies, min_quality: minQuality, whole_video_min_coverage: wholeVideoMinCoverage }, reasons, labels: decisions };
}

function svgWrap(contents, title) {
  return `<svg viewBox="0 0 500 245" role="img" aria-label="${esc(title)}" xmlns="http://www.w3.org/2000/svg"><rect width="500" height="245" fill="#f5f7fa"/>${contents}</svg><span class="visual-watermark">SYNTHETIC ILLUSTRATION</span>`;
}
function visualFor(sample) {
  if (sample.visual === "chart") return svgWrap(`<rect x="48" y="18" width="410" height="207" rx="4" fill="white" stroke="#dce3ec"/><g stroke="#e9eef4">${[65,105,145,185].map((y) => `<path d="M88 ${y}H425"/>`).join("")}</g><path d="M88 40V185H425" fill="none" stroke="#8391a4"/><path d="M88 154L155 142L222 113L289 125L356 77L423 51" stroke="#078d7d" stroke-width="3" fill="none"/><path d="M88 172L155 163L222 148L289 143L356 129L423 105" stroke="#8b78cf" stroke-width="3" fill="none"/><g fill="#078d7d">${[[88,154],[155,142],[222,113],[289,125],[356,77],[423,51]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3"/>`).join("")}</g><g font-size="9" fill="#8593a7" font-family="sans-serif"><text x="248" y="210">Step</text><text transform="translate(68 125) rotate(-90)">Response</text><text x="75" y="188">0</text><text x="64" y="68">100</text><text x="85" y="200">0</text><text x="419" y="200">5</text><text x="333" y="35">A</text><text x="390" y="35">B</text></g><path d="M311 31h15" stroke="#078d7d" stroke-width="3"/><path d="M367 31h15" stroke="#8b78cf" stroke-width="3"/><rect x="81" y="43" width="351" height="148" fill="none" stroke="#4ea99d" stroke-dasharray="4 4" opacity=".8"/><rect x="93" y="47" width="76" height="17" rx="2" fill="#e6f2ed"/><text x="99" y="59" fill="#2f8474" font-size="8" font-family="monospace">E1: line chart</text>`, "合成折线图，包含两条连续数据序列、坐标轴和定位区域");
  if (sample.visual === "micro") {
    const dots = Array.from({ length: 58 }, (_, i) => { const x = 93 + ((i * 67 + 17) % 310); const y = 31 + ((i * 43 + 11) % 180); const r = 5 + ((i * 7) % 14); return `<ellipse cx="${x}" cy="${y}" rx="${r}" ry="${r*.75}" fill="${["#8d9fae", "#b7c7d1", "#6e8795", "#c9d6dd"][i % 4]}" opacity=".65"/>`; }).join("");
    return svgWrap(`<defs><clipPath id="micro-clip"><rect x="83" y="20" width="334" height="205" rx="3"/></clipPath></defs><rect x="83" y="20" width="334" height="205" fill="#d6e0e5" stroke="#c3d0db"/> <g clip-path="url(#micro-clip)">${dots}</g><rect x="95" y="31" width="122" height="19" rx="2" fill="#f8fafc" opacity=".9"/><text x="102" y="44" fill="#627488" font-family="monospace" font-size="9">Instrument: unknown</text><rect x="282" y="192" width="122" height="20" rx="2" fill="#f8fafc" opacity=".9"/><text x="289" y="206" fill="#627488" font-family="monospace" font-size="9">Scale bar: missing</text>`, "合成颗粒纹理，仪器与比例尺未知");
  }
  if (sample.visual === "cad") return svgWrap(`<defs><pattern id="cad-grid" width="23" height="23" patternUnits="userSpaceOnUse"><path d="M23 0H0V23" fill="none" stroke="#dbe5ed" stroke-width=".7"/></pattern></defs><rect x="55" y="15" width="390" height="215" fill="url(#cad-grid)"/><path d="M151 139L246 80L356 125L263 189Z" fill="#9ab3c8" stroke="#64829c"/><path d="M151 139V166L263 216V189Z" fill="#708fa9" stroke="#64829c"/><path d="M263 189L356 125V153L263 216Z" fill="#b5cbdc" stroke="#64829c"/><path d="M215 119V63L257 39L299 56V113L257 141Z" fill="#9eb7cc" stroke="#64829c"/><path d="M257 39V141L299 113V56Z" fill="#bcd0df" stroke="#64829c"/><ellipse cx="255" cy="92" rx="19" ry="25" transform="rotate(-27 255 92)" fill="#f5f7fa" stroke="#64829c" stroke-width="4"/><path d="M119 174L234 226M373 136L283 201" stroke="#8f7ec1" stroke-dasharray="4 4"/><rect x="321" y="25" width="103" height="32" fill="#fff4e7" stroke="#ead2b2" rx="3"/><text x="331" y="38" font-family="monospace" font-size="8" fill="#a47846">LICENSE</text><text x="331" y="50" font-family="monospace" font-size="9" fill="#a47846">unknown</text>`, "合成 CAD 零件渲染示意，来源许可证未知");
  const sparse = sample.visual === "sparse";
  const frames = [0,1,2,3].map((i) => `<g transform="translate(${37 + i*112},30)"><rect width="94" height="133" rx="3" fill="${sparse && (i === 1 || i === 2) ? "#e7ecf3" : "#e0eceb"}" stroke="#cbd8e3"/>${sparse && (i === 1 || i === 2) ? '<text x="47" y="63" text-anchor="middle" font-family="monospace" font-size="21" fill="#b4bfce">?</text><text x="47" y="85" text-anchor="middle" font-size="8" fill="#8f9bad">not observed</text>' : `<path d="M25 55V102Q25 111 34 111H61Q69 111 69 102V55" fill="none" stroke="#78999b" stroke-width="2"/><path d="M27 ${84-i*3}H67V102Q67 109 59 109H35Q27 109 27 102Z" fill="${i>1 ? "#83b9ac" : "#a7c9d2"}"/><path d="M${42+i*4} 29L${49-i} 89" stroke="#566f84" stroke-width="3"/>${i===1 || i===2 ? '<path d="M36 93Q48 85 60 93Q48 100 36 93" fill="none" stroke="#8a79bc" stroke-width="1.5"/>' : ""}`}<text x="47" y="125" text-anchor="middle" font-family="monospace" font-size="8" fill="#7a8a9f">${sparse ? ["00:02","00:35","01:25","01:58"][i] : ["00:01","00:04","00:08","00:11"][i]}</text></g>`).join("");
  const timeline = sparse ? `<rect x="40" y="190" width="420" height="10" rx="3" fill="#e2e7ee"/><g fill="#93bcb4"><rect x="40" y="190" width="14" height="10" rx="2"/><rect x="236" y="190" width="14" height="10" rx="2"/><rect x="446" y="190" width="14" height="10" rx="2"/></g><text x="250" y="223" text-anchor="middle" font-size="9" fill="#9a7953" font-family="sans-serif">已检查 12 / 120 秒 · 未检查区域保持 unknown</text>` : `<rect x="40" y="190" width="420" height="10" rx="3" fill="#dfe7ef"/><rect x="145" y="190" width="210" height="10" rx="2" fill="#80bfb1"/><path d="M145 183V207M355 183V207" stroke="#498a7b"/><g fill="#718498" font-family="monospace" font-size="8"><text x="37" y="216">0s</text><text x="140" y="216">3s</text><text x="349" y="216">9s</text><text x="447" y="216">12s</text></g><text x="250" y="181" text-anchor="middle" fill="#458778" font-size="9">可见混合动作 / event.fluid_flow</text>`;
  return svgWrap(frames + timeline, sparse ? "合成视频时间线，120 秒中只观察三个短窗口，其他窗口未知" : "合成实验视频关键帧，混合动作位于 3 至 9 秒");
}

function renderSamples() {
  const visible = fixtures.filter((f) => f.mode === mode);
  $("#sample-count").textContent = String(visible.length).padStart(2, "0");
  $("#sample-list").innerHTML = visible.map((sample) => `<button type="button" class="sample-item" data-sample="${sample.id}" aria-pressed="${sample.id === current.id}"><span class="sample-kind">${sample.kind}</span><strong>${sample.title}</strong><small>${sample.note}</small></button>`).join("");
  $("#sample-list").querySelectorAll("button").forEach((button) => button.addEventListener("click", () => { current = fixtures.find((f) => f.id === button.dataset.sample); renderSamples(); renderSample(); $("#sample-list").querySelector(`[data-sample="${current.id}"]`)?.focus(); }));
}

function renderSample() {
  $("#download-status").textContent = "";
  $("#sample-id").textContent = `${current.id} / ${current.mode.toUpperCase()}`;
  $("#sample-title").textContent = current.title;
  $("#sample-description").textContent = current.description;
  $("#sample-visual").innerHTML = visualFor(current);
  $("#candidate-list").innerHTML = current.candidates.map((c, i) => `<div class="candidate-row"><span class="candidate-index">C${i+1}</span><div><strong>${esc(c.name)}</strong><p>${esc(c.explanation)}</p><div class="candidate-labels">${c.labels.map((id) => `<span class="tag" title="${esc(id)}">${esc(labelName(id))}</span>`).join("")}</div></div></div>`).join("");
  $("#evidence-list").innerHTML = current.evidence.map((e) => `<article class="evidence-row ${e.support ? "" : "counter"}"><div class="evidence-meta"><span>${e.id} · ${esc(e.family)}</span><span>质量 ${e.quality.toFixed(2)}</span></div><strong>${esc(e.title)}</strong><p>${esc(e.location)}<br>${esc(e.detail)}</p></article>`).join("");
  renderDecision();
}

function taskFor(decision) {
  const activeLabels = decision.labels.filter((d) => d.state === "provisional").map((d) => d.label_id);
  const targetLabels = current.target?.label_ids || (current.target?.event_id ? [current.target.event_id] : []);
  const eligible = decision.status === "provisional" && targetLabels.length > 0 && targetLabels.every((id) => activeLabels.includes(id));
  return {
    fixture_kind: "synthetic_demo",
    sample_id: current.id,
    status: eligible ? "candidate_task_requires_gold_validation" : "blocked_pending_review",
    export_to_training: false,
    reason: "No independent held-out calibration or human gold validation has been performed.",
    prompt: current.mode === "video" ? "定位可见动作，返回事件 ID、时间区间与证据 ID；证据不足时返回 unknown。" : "识别可见图像形态，返回标签 ID 与区域证据；学科证据不足时返回 unknown。",
    supported_provisional_labels: activeLabels,
    target: eligible ? current.target : null,
    verifier: eligible ? (current.mode === "video" ? { type: "temporal_iou_against_gold", requires: ["valid_event_id", "valid_interval", "evidence_reference"], no_reward_for_unsupported_claims: true } : { type: "set_match_against_gold", requires: ["valid_taxonomy_ids", "label_precision", "evidence_reference"], no_reward_for_unsupported_claims: true }) : null,
    lineage: { source: current.id, observation_version: "synthetic-v1", policy: decision.thresholds },
  };
}

function renderDecision() {
  const decision = assess(current);
  $("#family-value").textContent = String(decision.thresholds.min_families);
  $("#quality-value").textContent = decision.thresholds.min_quality.toFixed(2);
  const status = $("#decision-status");
  status.className = `decision-status ${decision.status}`;
  status.textContent = ({ provisional: "局部标签暂定通过", review: "进入人工复核", quarantine: "来源权利隔离" })[decision.status];
  $("#decision-reasons").innerHTML = decision.reasons.map((reason) => `<p class="reason-item"><span aria-hidden="true">·</span><span>${esc(reason)}</span></p>`).join("");
  $("#label-decisions").innerHTML = decision.labels.map((d) => `<div class="label-decision"><div class="label-decision-top"><strong>${esc(labelName(d.label_id))}</strong><span class="${d.state}">${d.state === "provisional" ? "暂定" : "复核"}</span></div><p>${d.supporting_family_count} 证据组 / ${d.evidence_ids.length} 条支持记录${d.block_reasons.length ? " · " + esc(d.block_reasons.join(" ")) : ""}</p></div>`).join("");
  $("#task-json").textContent = JSON.stringify(taskFor(decision), null, 2);
}

function renderTaxonomy() {
  const query = $("#taxonomy-search").value.trim().toLowerCase();
  const filtered = taxonomy.filter((item) => (selectedAxis === "all" || item.axis === selectedAxis) && `${item.id} ${item.name} ${item.evidence} ${item.boundary}`.toLowerCase().includes(query));
  $("#taxonomy-rows").innerHTML = filtered.length ? filtered.map((item) => `<tr><td><strong>${esc(item.name)}<span class="axis-label">${item.axisName}</span></strong><code>${esc(item.id)}</code></td><td>${esc(item.evidence)}</td><td>${esc(item.boundary)}</td></tr>`).join("") : '<tr><td colspan="3" class="empty-result">没有匹配标签。可尝试“显微”“事件”或“evidence”。</td></tr>';
  $("#taxonomy-summary").textContent = `显示 ${filtered.length} / ${taxonomy.length} 个代表性标签。标签 ID 来自版本化本体；演示只展示部分策略，生产应使用后端完整校验。`;
}

document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
  mode = button.dataset.mode;
  current = fixtures.find((f) => f.mode === mode);
  document.querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
  renderSamples(); renderSample();
}));

function setPanel(name, moveFocus = false) {
  activePanel = name;
  document.querySelectorAll("[data-panel]").forEach((button) => {
    const selected = button.dataset.panel === name;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    $(`#panel-${button.dataset.panel}`).hidden = !selected;
    if (selected && moveFocus) button.focus();
  });
}
document.querySelectorAll("[data-panel]").forEach((button) => {
  button.addEventListener("click", () => setPanel(button.dataset.panel));
  button.addEventListener("keydown", (event) => {
    const panels = ["candidates", "evidence", "task"];
    let next;
    if (event.key === "ArrowRight") next = panels[(panels.indexOf(activePanel) + 1) % panels.length];
    if (event.key === "ArrowLeft") next = panels[(panels.indexOf(activePanel) + panels.length - 1) % panels.length];
    if (event.key === "Home") next = panels[0];
    if (event.key === "End") next = panels[panels.length - 1];
    if (next) { event.preventDefault(); setPanel(next, true); }
  });
});
document.querySelectorAll("[data-axis]").forEach((button) => button.addEventListener("click", () => {
  selectedAxis = button.dataset.axis;
  document.querySelectorAll("[data-axis]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
  renderTaxonomy();
}));
$("#taxonomy-search").addEventListener("input", renderTaxonomy);
$("#family-threshold").addEventListener("input", renderDecision);
$("#quality-threshold").addEventListener("input", renderDecision);
$("#download-sample").addEventListener("click", () => {
  const decision = assess(current);
  const blob = new Blob([JSON.stringify({ demo_only: true, fixture: current, decision, training_task: taskFor(decision) }, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = `${current.id.toLowerCase()}-demo.json`;
  anchor.hidden = true;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  $("#download-status").textContent = `已发起 ${anchor.download} 下载；内容为页面合成演示格式，不能直接作为后端观测输入。`;
  setTimeout(() => URL.revokeObjectURL(url), 30000);
});
renderSamples(); renderSample(); renderTaxonomy();
