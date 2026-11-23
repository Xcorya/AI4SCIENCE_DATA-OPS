# AI4Science Visual Flywheel

面向科研图像与视频的精细分类、证据验证和训练数据构造。

本项目把“模型给出标签”推进为“每个标签都有区域或时间证据，并满足独立验收条件”。通过多轴标签、Best-of-3 候选、多轮补证据、方法专属检查、时序约束和选择性接收，构建可追溯的数据飞轮。

**当前交付：理论方案 + 可运行策略原型 + 静态交互页面。** Python 程序处理上游模型或人工提供的结构化观测，不直接识别媒体；全部演示样本是合成数据。项目尚未完成真实图像/视频精度评测或模型训练实验。

## 项目内容

| 内容 | 入口 |
| --- | --- |
| 完整技术说明与算法 | [技术说明](docs/whitepaper.md) |
| 多轴层级标签与判断边界 | [标签规范](docs/taxonomy.md) · [机器配置](configs/taxonomy.json) |
| 人工标注与仲裁 | [标注指南](docs/annotation-guide.md) |
| 主动采样、难负例与数据闭环 | [数据策略](docs/data-strategy.md) |
| Bo3 与 Verifier 提示词 | [提示词与编排](docs/prompts.md) |
| 视觉模型、视频处理与服务接入 | [接入指南](docs/model-adapters.md) |
| 输入输出和认证格式 | [代码契约](docs/code-contract.md) |
| 精确率、覆盖率、成本与训练收益 | [评测协议](docs/evaluation.md) |
| 可直接使用的项目介绍 | [项目介绍](docs/project-introduction.md) |
| GitHub 仓库与 Pages 发布 | [上传指南](docs/github-guide.md) |
| 公开研究与组件依据 | [参考资料](docs/references.md) |

## 核心设计

- **六轴标签**：表达形态、采集/生成方式、专业学科、视频形式、时间事件、任务候选分别建模。
- **逐标签证据**：整图、面板、区域、镜头与事件各自定位；父类通过不自动确认子类。
- **Bo3 与反证**：三份候选用于扩大搜索；依赖族去重后再验证，不把三次同源输出当作三份独立事实。
- **视频时序**：检查事件区间、实际观测片段、时间顺序与来源时间线；静帧和字幕不能独自证明动作。
- **独立认证**：tune 选阈值，audit 做精确二项置信验收；证书绑定策略、本体、管线版本和来源 cohort。
- **受控训练导出**：未认证结果保留为 provisional；RL 还需可信参考，奖励函数按标签与定位检查最终输出。

98% 或 99% 可作为验收目标，不能由模型自行声明。提高精确率通常需要降低自动接收率；两者应与成本一起报告。

## 快速运行

Python 3.10+，运行参考算法不需要安装第三方依赖或配置 API 密钥。在仓库根目录执行：

```bash
python3 scripts/run_demo.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/verify_workflow.py
```

输出在 `work/demo/`：

```text
decisions.jsonl        每个标注单元的逐标签决策与原因
sft_candidates.jsonl  满足规则的候选监督数据
rl_candidates.jsonl   满足规则并有核准参考的候选任务
summary.json          本次演示状态汇总
```

合成示例不能认证或进入训练，因此演示的 SFT/RL 导出为空。这一行为用于验证发布门槛；不是系统没运行。

接入自己的观测：

```bash
PYTHONPATH=src python3 -m visual_flywheel run \
  --input your-observations.jsonl \
  --calibration your-calibration.json \
  --output-dir work/run
```

没有匹配证书时可以运行并查看暂定结果，但不能生成训练导出。真实来源、模型观测、金标与证书的生产者需要可信；本地 JSON 格式不提供抗篡改能力。

也可以用 `python3 -m pip install .` 安装，再运行 `visual-flywheel --version` 或 `visual-flywheel run ...`。安装包自带默认标签与策略，不依赖当前目录。源码运行读取仓库的 `configs/`；`--policy` 和 `--taxonomy` 可显式覆盖。软件规则变更后，引擎版本参与证书指纹，旧证书需要重新验收。

`verify_workflow.py` 在临时目录模拟上游信任声明，验证校准、导出、奖励和拒错路径；模拟证书与数据自动删除，不产生真实精度声明。页面规则可用 Node.js 18+ 复测：`node tests/web_policy.cjs`。

当前修订为 **0.1.1**。完整实测结果及已修复问题见 [验证报告](VALIDATION.md)。

## 查看交互页面

```bash
python3 scripts/build_site_docs.py
python3 -m http.server 8000 --directory docs/site --bind 127.0.0.1
```

打开 [本地页面](http://127.0.0.1:8000)。可切换图像/视频示例，查看三份候选、证据账本、阈值变化、拒识原因与候选任务 JSON，并搜索代表性标签。页面是独立的简化规则演示；Python 策略是可复算的参考实现，两者都不调用真实视觉模型。

仓库附带手动触发的 GitHub Pages 工作流，发布目录仅为 `docs/site`。源码上传和页面发布步骤见 [上传指南](docs/github-guide.md)。

## 项目状态

| 已提供 | 需要接入与实测 |
| --- | --- |
| 标签配置、标注规范、算法与数据策略 | 授权来源采集、近重复聚类、媒体存储 |
| 确定性证据策略与独立认证工具 | 图像/视频模型、OCR、镜头与面板解析 |
| 标签/定位任务与奖励示例 | 真实金标、跨来源测量、专家审核 |
| 合成失败案例、单元测试、CI 与页面 | 批量生产吞吐、模型训练和收益实验 |

原生 CAD、音频和论文全文推理可以沿用资产、证据、验证器与任务接口扩展。本版本聚焦图像和视频。

## 许可

仓库原创代码、文档、页面与合成示例采用 [MIT License](LICENSE)。外部媒体、模型和数据集保留各自许可；本仓库没有打包第三方原始媒体、模型权重或内部文档。
