# 上传 GitHub 与发布演示页面

建议仓库名 `ai4s-visual-flywheel`。建议描述：`Evidence-grounded image and video curation for AI4Science: taxonomy, verification, calibration, and verifiable training tasks.`

## 1 上传源码

在 GitHub 新建空仓库。若导入本项目，不额外勾选自动创建 README、LICENSE 或 gitignore，以免与本地文件冲突。[GitHub 新建仓库说明](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)

解压交付包后，在 `ai4s-visual-flywheel` 目录中执行。将示例远程地址替换为你实际拥有的仓库：

```bash
git init -b main
git add .
git commit -m "Add AI4Science visual flywheel blueprint and policy reference"
git remote add origin https://github.com/YOUR_ACCOUNT/ai4s-visual-flywheel.git
git push -u origin main
```

包中没有预设远程仓库或登录凭据。工作目录和本地生成数据由 `.gitignore` 忽略。仓库的测试工作流会运行标准库单元测试、合成演示和静态页面文件检查。

## 2 发布 GitHub Pages

本项目按 GitHub 官方静态 Pages 工作流配置，使用 `docs/site` 作为站点产物，手动触发发布。[GitHub 官方工作流](https://github.com/actions/starter-workflows/blob/main/pages/static.yml)

1. 在仓库 Settings → Pages 中选择 GitHub Actions 作为构建来源。
2. 进入 Actions → Publish demo to GitHub Pages。
3. 点击 Run workflow，选择 main 并运行。
4. 工作流完成后，从 deployment 环境或 Pages 设置读取实际站点 URL。

工作流会重新生成静态说明页，再上传站点目录。更新代码并不会自动发布页面；需要再次手动运行。是否能发布以及访问范围受账户、仓库与组织设置影响，以 GitHub 返回结果为准。

## 3 仓库首页建议

Topics 可选：`ai4science`、`multimodal`、`data-curation`、`image-classification`、`video-understanding`、`reinforcement-learning`、`verifiable-rewards`。

首页 README 已说明当前实现边界。不要在 About 或 Release 中写“99% 精度”“已批量训练”之类尚未实测的结论。版本说明可以使用：

> v0.1.0 提供图像与视频多轴标签、证据筛选策略、独立精确率认证工具、标签与定位任务奖励、合成测试及交互演示。真实视觉推理、金标评测和模型训练作为接入工作继续开展。

## 4 修改后验证

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/run_demo.py
python3 scripts/build_site_docs.py
python3 scripts/check_site.py
```

策略或 taxonomy 更新后，旧证书应失效。上游模型、提示词或预处理变化时，同时更新 `configs/policy.json` 的管线版本，再重新校准。
