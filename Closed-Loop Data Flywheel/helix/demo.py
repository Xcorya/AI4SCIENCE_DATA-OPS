"""Original synthetic fixtures. They are not measurements from external research."""
import json
from .store import now

SEEDS = [
    ("physics", "table", "湍流通道 · 压力观测序列", "pressure", [12, 18, 24, 30], "Pa"),
    ("physics", "image", "相空间轨迹 · 振幅观测", "amplitude", [1.2, 2.4, 1.8, 3.6], "mm"),
    ("chemistry", "table", "催化动力学 · 浓度时间序列", "concentration", [8, 6, 4, 2], "mmol/L"),
    ("chemistry", "molecule", "分子构象 · 键长观测", "bond_length", [1.1, 1.3, 1.5, 1.7], "angstrom"),
    ("biology", "sequence", "合成序列 · 片段长度", "sequence_length", [24, 32, 40, 48], "bp"),
    ("biology", "video", "细胞迁移 · 帧间位移标注", "displacement", [2, 3, 5, 8], "um"),
    ("mathematics", "paper", "优化实验 · 目标函数记录", "objective", [16, 8, 4, 2], "dimensionless"),
    ("astronomy", "image", "恒星测光 · 辐射通量", "flux", [10, 12, 14, 16], "mJy"),
    ("earth", "geospatial", "流域观测 · 海拔剖面", "elevation", [400, 360, 320, 280], "m"),
    ("engineering", "cad", "参数化构件 · 厚度公差序列", "thickness", [2, 2.1, 1.9, 2.2], "mm"),
    ("engineering", "code", "求解器基准 · 运行时间", "runtime", [12, 10, 8, 6], "s"),
    ("physics", "audio", "声学测量 · 频率标注", "frequency", [200, 400, 600, 800], "Hz"),
    ("earth", "table", "许可待审 · 地表温度观测", "temperature", [11, 12, 13, 15], "degC"),
    ("astronomy", "table", "封闭基准 · 波长观测", "wavelength", [400, 500, 600, 700], "nm"),
]


def seed(store):
    created = 0
    for i, (domain, modality, title, quantity, values, unit) in enumerate(SEEDS):
        facts = {"quantity": quantity, "values": values, "unit": unit}
        text = json.dumps(facts, ensure_ascii=False, sort_keys=True)
        checksum = store.put_object(text.encode())
        asset = {
            "title": title, "source_id": "helix-original-fixture-" + str(i),
            "source_url": "demo://original/" + str(i), "modality": modality,
            "discipline": domain, "license": "unknown" if i == 12 else "CC0-1.0",
            "facts": facts, "text": text, "is_demo": True,
            "benchmark": i == 13, "object_sha256": checksum, "byte_size": len(text.encode()),
            "storage_status": "annotation_stored",
            "note": "原创合成观测。此记录保存 JSON 标注；未宣称下载图片、视频或 CAD 原文件。",
            "created_at": now(),
        }
        _, added = store.add_asset(asset)
        created += int(added)
    return {"created": created, "total": len(SEEDS)}
