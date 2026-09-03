# MechabellumMods

钢铁指挥官（Mechabellum）社区 MOD 目录仓库。本仓库存放可供 [Mechabellum Mod 管理器](https://github.com/llxlzx/MechabellumModManager) 拉取的 MOD 清单与文件。

Community MOD catalog for Mechabellum. Files here are fetched by the [Mechabellum Mod Manager](https://github.com/llxlzx/MechabellumModManager).

> **⚠️ AI 生成声明 / AI-generated notice**  
> 本 README 的中英文教程主要由 AI 辅助撰写与翻译，可能存在表述偏差。请以仓库实际结构与 CI 校验为准。  
> **This README’s Chinese/English guides were largely AI-assisted and may contain inaccuracies. Prefer the real repo layout and CI checks.**

## 语言 / Language

- 中文：[投稿与举报](#投稿与举报--submit--report) · [目录结构](#目录结构--layout) · [catalog 字段](#catalogjson-字段--fields)
- English: [Submit & Report](#投稿与举报--submit--report) · [Layout](#目录结构--layout) · [catalog fields](#catalogjson-字段--fields)
- 快捷页 / Quick page: **[docs/submit.html](docs/submit.html)**（四个一键 mailto 按钮）

---

<a id="投稿与举报--submit--report"></a>

## 投稿与举报 / Submit / Report

**推荐方式：发邮件。** 作者**不需要** Fork、也不需要自己开 Pull Request。  
维护者用 AI / 人工审核后，会把通过的 Mod 上传到本 GitHub 仓库；玩家在管理器里点 **Mod 浏览 → 刷新目录** 就能看到。

**Preferred path: email.** Authors do **not** need to Fork or open a Pull Request.  
After review, maintainers upload accepted mods into this GitHub repo; players **Browse Mods → Refresh catalog** in the manager.

### 收件邮箱 / Inbox

**llxmod@foxmail.com**

静态快捷页（可点按钮打开邮件模板）：[docs/submit.html](docs/submit.html)

### 规则（作者必读）/ Rules

1. **主题必须以**下表四个前缀之一开头（直接复制，方便 QQ 邮箱过滤）。  
   Subject **MUST** start with one of the four prefixes below (copy-paste).
2. **一封邮件只办一件事**（一条投稿 / 一次更新 / 一条举报 / 一条建议）。  
   One email = one request.
3. **投稿 / 更新**：必须附加 `.dll`；可选 `preview.png` 介绍图。附件合计大约 **>40MB** 时，请在正文写网盘链接，不要硬塞超大附件。  
   Submit/Update: attach `.dll` (required); optional `preview.png`. If attachments are huge (~>40MB), put a netdisk link in the body.
4. **不要**主动发送源码（除非维护者另行索要）。  
   Do not send source code unless asked.
5. （可选）熟悉 GitHub 的作者仍可自行 Fork + PR；默认路径是邮件。  
   Advanced users may still PR; email is the default path.

### 主题前缀（必须精确）/ Subject prefixes (exact)

| 类型 / Type | 主题格式 / Subject pattern |
|-------------|----------------------------|
| 新 Mod / New mod | `[Mod投稿/Submit] {ModName}` |
| 更新已有 / Update | `[Mod更新/Update] {ModName}` |
| 举报 / Report | `[Mod举报/Report] {ModName}` |
| 管理器建议 / Feedback | `[管理器建议/Feedback] {ShortTitle}` |

### 正文模板 / Body templates

**投稿 (Submit) — 附加 DLL + 可选 preview.png**

```
【类型 / Type】投稿 / Submit（新 Mod）
【Mod 名称 / Name】
【作者 / Author】
【版本 / Version】
【一句话简介 / Summary】
【游戏端 / Game】正式服 / 测试服 / 两者（Official / Test / Both）
【联系方式 / Contact】（可选）
【备注 / Notes】
```

**更新 (Update) — 附加新 DLL**

```
【类型 / Type】更新 / Update
【Mod 名称 / Name】
【作者 / Author】
【原版本 → 新版本 / Version】
【更新说明 / Changelog】
【联系方式 / Contact】（可选）
```

**举报 (Report)**

```
【类型 / Type】举报 / Report
【Mod 名称 / Name】
【Mod Id】（若知道）
【来源 / Source】社区目录 / 本地库（Catalog / Library）
【类别 / Category】作弊相关 / 病毒或恶意 / 与游戏无关 / 其他（Cheat / Malware / Unrelated / Other）
【说明 / Details】
【管理器版本 / App】
```

**建议 (Feedback)**

```
【类型 / Type】管理器建议 / Feedback
【标题 / Title】
【详细说明 / Details】
【管理器版本 / App】（可选）
【联系方式 / Contact】（可选）
```

管理器内「投稿 Mod」「举报」会按界面语言打开 QQ 邮箱网页（中文）或 Gmail 写信页（其他语言），并复制主题/正文模板；若网页未打开，请手动发信到 **llxmod@foxmail.com** 并粘贴模板。

维护者将在合理时间内审阅并处理您的来信。受日常生活与个人事务安排影响，处理进度或有短暂延误，敬请谅解并耐心等待。请勿重复发送同一内容。

The maintainer will review and process your message within a reasonable time. Handling may be briefly delayed due to daily life and personal schedule; thank you for your patience. Please do not resend the same request.

---

## 目录结构 / Layout

```
MechabellumMods/
  README.md
  docs/submit.html      # mailto helper page
  catalog.json          # MOD catalog / 目录清单
  mods/
    <mod-id>/
      <ModName>.dll     # MelonLoader plugin
      preview.png       # optional preview
```

## catalog.json 字段 / Fields

Root object:

| Field | Meaning |
|------|------|
| `updatedAt` | Catalog update time (ISO 8601, e.g. `2026-09-03T12:00:00Z`) |
| `mods` | Array of MOD entries |

Each MOD entry:

| Field | Meaning | Example |
|------|------|------|
| `id` | Unique id (**lowercase letters/digits/hyphens**, same as folder name) | `show-grid` |
| `name` | Display name | `Show Grid` |
| `author` | Author | `YourName` |
| `version` | Version | `1.0.0` |
| `updatedAt` | MOD date | `2026-09-03` |
| `summary` | Short description | `Toggle grid with G` |
| `file` | DLL path relative to repo root | `mods/show-grid/ShowGrid.dll` |
| `preview` | Optional preview path | `mods/show-grid/preview.png` |
| `type` | Always | `MelonMod` |

维护者合并进本仓库后的路径与字段须符合上表与 CI（Validate catalog）。作者走邮件投稿时，**不必**自己改 `catalog.json`。

---

## 许可与免责 / License & Disclaimer

详见根目录 [`LICENSE`](LICENSE)。摘要：

1. 作者自行公布的许可/条款优先适用于该 Mod。  
2. 否则，邮件投稿即授权维护者以非商业方式托管、分发与展示（作者保留著作权）。  
3. 目录文案/元数据默认非商业社区使用（建议 CC BY-NC-SA 4.0）；不自动覆盖第三方二进制。  
4. 第三方二进制风险自负；收录不代表背书；与游戏官方无从属关系。  
5. 处理时效见上文（合理时间内审阅；或有短暂延误；请勿重复发送）。

See root [`LICENSE`](LICENSE). Author terms win; otherwise email submission grants non-commercial host/distribute/list permission. Catalog metadata defaults to non-commercial community use (CC BY-NC-SA 4.0 suggested). Third-party binaries at your own risk; no affiliation with the game publisher.


## 相关项目 / Related

- Mod Manager: https://github.com/llxlzx/MechabellumModManager
