# 参考资料与采用范围

以下是公开原始论文、项目或官方说明，核对日期为 2026 年 11 月 20 日。本项目的组合架构、标签体系和数据配方是工程设计提案；下列来源不证明该组合已经达到任何精确率或训练收益。

| 资料 | 本项目采用的概念 | 不据此声称 |
| --- | --- | --- |
| [SigLIP 2](https://arxiv.org/abs/2502.14786) | 图文表征、路由与检索组件候选 | 相似度是本域正确概率 |
| [Qwen2.5-VL Technical Report](https://arxiv.org/abs/2502.13923) | 文档、图表和视频的结构化提名组件候选 | 任意科学细标签已可靠 |
| [SAM 2](https://arxiv.org/abs/2408.00714) | 图像/视频分割与对象追踪 | 掩码能判定专业语义 |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | 镜头切分工具候选 | 镜头边界就是事件边界 |
| [NIST Confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm) | 二项比例的置信区间与精确反演 | 相关帧是独立试验 |
| [Conformal Risk Control](https://arxiv.org/abs/2208.02814) | 区分可控制风险与普通模型分数 | 普通集合覆盖就是 precision 保证 |
| [Scaling Laws for Reward Model Overoptimization](https://proceedings.mlr.press/v202/gao23h.html) | 代理奖励与 BoN 过度优化的风险 | 更大 N 必然提高真实质量 |
| [DeepSeekMath](https://arxiv.org/abs/2402.03300) | GRPO 等训练端可消费奖励任务 | 本仓库运行或复现了模型训练 |
| [ChartQA](https://arxiv.org/abs/2203.10244) | 图表视觉与运算的分层任务 | 可把外部测试题混进训练 |
| [MMMU](https://arxiv.org/abs/2311.16502) | 专业学科多模态评测思路 | 本方案覆盖其全部任务 |
| [SciCap](https://scicap.ai/) | 科学配图与上下文的组织参考 | 网站可访问即允许全量再分发 |

外部数据与模型逐项检查其自身许可。本仓库未打包上述项目代码、权重、数据或论文媒体。
