from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("HELIX_DATA_DIR", ROOT / "data")).expanduser()
MODALITIES = {
    "paper": "论文 / 文本", "image": "科研图像", "video": "实验视频",
    "cad": "CAD / 几何", "molecule": "分子 / 晶体", "table": "表格 / 时序",
    "code": "代码 / 仿真", "audio": "音频 / 波形", "geospatial": "地理 / 遥感",
    "sequence": "生物序列",
}
DISCIPLINES = {
    "physics": ("物理", "计算物理", "守恒与量纲", ["physics", "fluid", "quantum", "力学", "物理"]),
    "chemistry": ("化学", "物理化学", "谱学与动力学", ["chemistry", "spectra", "catalyst", "化学", "光谱"]),
    "biology": ("生物", "系统生物学", "序列与调控", ["biology", "protein", "gene", "生物", "蛋白"]),
    "mathematics": ("数学", "应用数学", "统计与优化", ["mathematics", "theorem", "optimization", "数学", "统计"]),
    "astronomy": ("天文", "天体物理", "观测与反演", ["astronomy", "galaxy", "stellar", "天文", "恒星"]),
    "earth": ("地球科学", "地球系统", "时空演化", ["climate", "geospatial", "earth", "地理", "气候"]),
    "engineering": ("工程与计算", "科学计算", "几何与系统", ["cad", "simulation", "engineering", "code", "计算", "工程"]),
}
GATES = [
    ("rights", "来源与许可", "许可明确、来源可追溯"),
    ("evidence", "证据完整性", "原始事实存在，引用与内容一致"),
    ("structure", "结构与一致性", "任务结构、数值、输出契约有效"),
    ("verification", "独立验证", "确定性答案验证器复算"),
    ("isolation", "基准隔离", "按原始来源家族划分，holdout 不进入训练"),
]
OPEN_LICENSES = {"CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "MIT", "Apache-2.0"}
VERSION = "helix-v1"
