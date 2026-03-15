# neo-bpsys.PluginMarket

[English README](./README_EN.md)

## 插件开发者提交流程

如果你要新增插件或更新已有插件，按下面流程提交即可。

1. Fork 本仓库。
2. 在你自己的仓库中修改或新增 `PluginManifests/<PluginId>.yml`。
3. 确保清单中的 `id` 唯一，且更新插件时不要修改已有 `id`。
4. 补齐或更新插件信息，例如 `name`、`description`、`version`、`apiVersion`、`author`、`url`、`downloadURL`。
5. 本地执行：

```powershell
python scripts/build-plugin-index.py
```

6. 确认根目录 `PluginIndex.json` 已生成或已同步更新。
7. 提交你的清单文件和更新后的 `PluginIndex.json`。
8. 向本仓库 `main` 分支发起 Pull Request。

## 清单要求

- 清单文件放在 `PluginManifests/`
- 文件名建议使用 `<PluginId>.yml`
- 当前只支持扁平的 `key: value` 结构
- 暂不支持嵌套对象或数组
- 每个清单必须包含非空且唯一的 `id`

示例：

```yml
id: "3DViewerIDV"
name: "3DViewerIDV"
description: "3D characters and scene support"
version: "0.04"
apiVersion: "2.0.0.0"
author: "jefcrb"
url: "https://github.com/jefcrb/3DViewerIDV"
downloadURL: "https://github.com/jefcrb/3DViewerIDV/releases/download/v0.04/repo-v0.04.zip"
```

## 常见提交场景

### 新增插件

- 新建一个自己的 `PluginManifests/<PluginId>.yml`
- 首次填写完整元数据
- 生成并提交 `PluginIndex.json`

### 更新插件

- 修改自己已有的清单文件
- 更新版本号、下载地址或描述等信息
- 保持原有 `id` 不变
- 重新生成并提交 `PluginIndex.json`

## 仓库自动化说明

当 `main` 分支收到包含 `PluginManifests/**/*.yml` 变更的 push 时，GitHub Actions 会自动：

1. 扫描全部插件清单。
2. 重建根目录 `PluginIndex.json`。
3. 仅在索引内容发生变化时自动提交并推回仓库。

生成后的 `PluginIndex.json` 使用插件 `id` 作为顶层 key。

## 校验规则

- 每一行都必须是合法的扁平 `key: value` 结构
- 以 `#` 开头的行会被当作注释
- 如果清单解析失败、缺少 `id` 或出现重复 `id`，GitHub Action 会失败
