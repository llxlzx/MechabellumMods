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
      preview.png       # 可选预览图
```

## catalog.json 字段说明

根对象：

| 字段 | 说明 |
|------|------|
| `updatedAt` | 目录整体更新时间（ISO 8601，例如 `2026-09-03T12:00:00Z`） |
| `mods` | MOD 条目数组 |

每个 MOD 条目：

| 字段 | 说明 | 示例 |
|------|------|------|
| `id` | 唯一标识（**小写英文/数字 + 短横线**，与文件夹名相同） | `show-grid` |
| `name` | 显示名称 | `地面格线 MOD` |
| `author` | 作者 | `你的名字` |
| `version` | 版本号 | `1.0.0` |
| `updatedAt` | 该 MOD 更新日期 | `2026-09-03` |
| `summary` | 一两句功能说明 | `按 G 开关格线` |
| `file` | DLL 相对仓库根目录的路径 | `mods/show-grid/ShowGrid.dll` |
| `preview` | 可选预览图路径 | `mods/show-grid/preview.png` |
| `type` | 固定填 | `MelonMod` |

---

## 新手投稿教程（网页操作，无需安装 Git）

适合第一次发 Mod 的作者。全程用浏览器即可，**不必**安装 Git 或会敲命令。

### 开始前准备

1. 注册并登录 [GitHub](https://github.com/signup)。
2. 准备好已经能在 MelonLoader 下加载的 **`.dll` 文件**（本仓库只收 DLL，不收未编译源码）。
3. 想好一个 **`id`**（文件夹名）：只用小写英文字母、数字和短横线，例如 `my-first-mod`。  
   **不要**用中文、空格或 `My Mod` 这种名字当 `id`。

### 第 1 步：Fork（复制）仓库到你的账号

1. 打开本仓库：https://github.com/llxlzx/MechabellumMods  
2. 右上角点 **Fork** → **Create fork**。  
3. 完成后浏览器会进入 **你的副本**，地址类似：  
   `https://github.com/你的用户名/MechabellumMods`  
   之后所有上传都在这个副本里做，不要直接改 `llxlzx` 的原仓库（你通常也没有写权限）。

### 第 2 步：上传 DLL

1. 在**你的 Fork** 页面，点进文件夹 **`mods`**。  
2. 点 **Add file** → **Upload files**。  
3. 把 DLL 拖进去。上传前先在本地建好路径再传，或上传后用网页改名，最终路径必须是：

   `mods/你的id/你的文件名.dll`  

   正确示例：`mods/my-first-mod/MyFirstMod.dll`  
   错误示例：直接放在 `mods/MyFirstMod.dll`（少了一层以 `id` 命名的文件夹）。

4. 页面下方 **Commit changes** → 确认提交。

（可选）同一文件夹里还可以再上传 `preview.png` 作为预览图。

### 第 3 步：改 `catalog.json`（让管理器能扫到你）

1. 回到你的 Fork **根目录**，点开 **`catalog.json`**。  
2. 点右上角铅笔图标 **Edit this file**。  
3. 找到 `"mods": [` 数组，在**最后一个已有条目的 `}` 后面**加一个英文逗号 `,`，再粘贴你的新条目。  
4. 示例（请改成你的信息；注意逗号和引号都是英文符号）：

```json
    {
      "id": "my-first-mod",
      "name": "我的第一个 Mod",
      "author": "你的名字",
      "version": "1.0.0",
      "updatedAt": "2026-09-03",
      "summary": "一句话说明这个 Mod 做什么。",
      "file": "mods/my-first-mod/MyFirstMod.dll",
      "type": "MelonMod"
    }
```

5. 把文件最上面的根字段 **`updatedAt`** 改成当前时间（UTC 即可），例如 `"2026-09-03T12:00:00Z"`。  
6. **Commit changes**。

注意：

- `id` 必须等于文件夹名；  
- `file` 必须等于你真实上传的路径；  
- 若加了预览图，再写 `"preview": "mods/my-first-mod/preview.png"`。

### 第 4 步：向原仓库提 Pull Request（申请合并）

1. 打开你的 Fork 首页，通常会出现黄色提示 **Contribute** / **Open pull request**，点进去。  
   若没有：点 **Contribute** → **Open pull request**，或打开  
   `https://github.com/llxlzx/MechabellumMods/compare`  
   并把右侧改成你的 Fork 分支。  
2. 标题建议：`Add my-first-mod` 或 `更新 xxx Mod 到 1.0.1`。  
3. 说明里写清：功能简介、是否 Melon Mod、测试过的游戏版本（如有）。  
4. 点 **Create pull request**。

### 第 5 步：等待合并

维护者合并后，玩家在管理器里点 **Mod 浏览 → 刷新目录** 就能看到。  
若 CI（Validate catalog）报错，按红色日志改路径 / `id` / JSON 后再推一次到你的 Fork（PR 会自动更新）。

### 更新已有 Mod

重复「上传新 DLL（覆盖同路径）→ 改 `catalog.json` 里对应条目的 `version` / `updatedAt` / `summary` → 再开 PR」。

---

## 举报

- 管理器会打开预填的 Issue（模板 `mod_report.md`，标签 `report`）。
- 也可在 GitHub「New issue」里选择 **Mod Report** 模板。
- 维护者请在仓库创建标签 **`report`**（Settings → Labels），否则管理器 URL 中的 `labels=report` 会被忽略。

```bash
gh label create report --repo llxlzx/MechabellumMods --color D73A4A --description "Mod reports from manager"
```

## 相关项目

- Mod 管理器：https://github.com/llxlzx/MechabellumModManager
