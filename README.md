# MechabellumMods

钢铁指挥官（Mechabellum）社区 MOD 目录仓库。本仓库存放可供 [Mechabellum Mod 管理器](https://github.com/llxlzx/MechabellumModManager) 拉取的 MOD 清单与文件。

## 目录结构

```
MechabellumMods/
  README.md
  catalog.json          # MOD 目录清单
  mods/
    <mod-id>/
      <ModName>.dll     # MelonLoader 插件
```

## catalog.json 字段说明

根对象：

| 字段 | 说明 |
|------|------|
| `updatedAt` | 目录整体更新时间（ISO 8601） |
| `mods` | MOD 条目数组 |

每个 MOD 条目：

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识（小写短横线，如 `show-grid`） |
| `name` | 显示名称 |
| `author` | 作者 |
| `version` | 版本号 |
| `updatedAt` | 该 MOD 更新日期（`YYYY-MM-DD`） |
| `summary` | 简短功能说明 |
| `file` | 相对仓库根目录的 DLL 路径 |
| `type` | 类型，当前为 `MelonMod` |

## 作者如何新增 / 更新 MOD

1. Fork 本仓库。
2. 在 `mods/` 下新建或更新对应目录，放入 DLL（例如 `mods/my-mod/MyMod.dll`）。
3. 在 `catalog.json` 的 `mods` 数组中新增或更新条目，并刷新根级 `updatedAt`。
4. 提交 Pull Request，说明版本变更与功能要点。
5. 合并后，管理器即可通过目录地址拉取最新清单与文件。

请确保：

- `id` 与文件夹名一致；
- `file` 路径真实存在且可下载；
- `version` / `updatedAt` / `summary` 与实际发布一致。

PR / push 会跑 GitHub Actions：`scripts/validate_catalog.py`（`id` 唯一、`file`/`preview` 路径存在）。

## 举报

- 管理器会打开预填的 Issue（模板 `mod_report.md`，标签 `report`）。
- 也可在 GitHub「New issue」里选择 **Mod Report** 模板。
- 维护者请在仓库创建标签 **`report`**（Settings → Labels），否则管理器 URL 中的 `labels=report` 会被忽略。

创建标签命令示例：

```bash
gh label create report --repo llxlzx/MechabellumMods --color D73A4A --description "Mod reports from manager"
```

## 相关项目

- Mod 管理器：https://github.com/llxlzx/MechabellumModManager
