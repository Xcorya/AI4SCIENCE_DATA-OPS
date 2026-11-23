# 上传 GitHub

推荐仓库名：`helix-science-flywheel`。

推荐描述：

> An evidence-first AI4Science data flywheel: multimodal asset ingestion, verifiable task synthesis, RL datasets, and evaluation feedback.

推荐 topics：`ai4science`、`data-flywheel`、`reinforcement-learning`、`synthetic-data`、`multimodal`、`scientific-machine-learning`。

## 发布内容

提交 README、代码、Web、configs、docs、原创 examples、tests、LICENSE 和 CI。`.gitignore` 已排除运行数据库、下载对象、导出目录、模型 checkpoint、密钥文件与缓存。

原始内部文档、内部链接、画板图片和实验表格不在仓库内。开源说明通过项目策略映射重新组织。

## 通过 Git 命令上传

先在自己的 GitHub 账号创建空仓库，不初始化 README。将下面 URL 替换成实际仓库地址：

```bash
cd helix
git init -b main
git add .
git status
git commit -m "Initial release: HELIX science data flywheel"
git remote add origin https://github.com/YOUR_ACCOUNT/helix-science-flywheel.git
git push -u origin main
```

如果 Git 提示未配置身份，设置自己的真实提交身份；不要使用项目工具代填的身份。上传前确认 `git status` 不包含运行数据或密钥。

## 用网页上传

也可解压项目 ZIP，把顶层目录中的文件拖入 GitHub 的 “Add file → Upload files”。注意提交 `.github` 和 `.gitignore` 等隐藏文件。

## 页面托管

当前页面依赖本地 Python API，不能直接在 GitHub Pages 上运行整个系统。GitHub 可展示 README 与文档；在线完整演示需要部署带后端的服务，并补齐认证、队列、资源配额和数据授权。

## 建议首个 Release

标题：`v0.1.0 — A runnable theory of the science data flywheel`

说明重点：可运行数据闭环、明确的理论/实现边界、完整中文手册、原创演示数据，以及欢迎贡献学科验证器。
