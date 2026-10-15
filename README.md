# KPL 每日赛程助手 · V1.0

一个**不用自购服务器**的网页 PWA：查看今天、明天、未来七天可用的 KPL 赛程。GitHub Actions 每天自动抓取公开网页，成功后部署 GitHub Pages；可选地通过 PushPlus 向自己微信推送当天比赛。

> 这是非官方个人练习项目。数据来自 [玩加电竞 KOG 赛程](https://wanplus.cn/kog/schedule) 及其单场详情页面，**并非稳定、官方授权的公开 API**。网站改版、风控、临时改期都可能影响结果；请以 [KPL 官网](https://kpl.qq.com/) 为准。数据获取失败不替换旧数据、不发提醒。项目没有实时直播比分能力。

## 文件结构

```text
kpl-schedule-assistant/
├── .github/workflows/
│   └── kpl-daily.yml              # 每天定时抓取、可选通知、部署 Pages
├── scripts/
│   ├── update_schedule.py          # 爬取赛程页，再爬取每场详情的原始开赛时间
│   └── notify.py                   # 有比赛才推送，按日期去重
├── docs/                           # GitHub Pages 的站点根目录
│   ├── index.html                  # 页面结构
│   ├── style.css                   # 页面样式
│   ├── app.js                      # 今天/明天/七天切换、加载 JSON
│   ├── sw.js                       # PWA 离线资源缓存
│   ├── manifest.webmanifest        # 添加到主屏幕的配置
│   ├── icons/                      # App 图标
│   └── data/schedule.json          # 抓取生成的数据（初始为空）
├── data/notification_state.json    # 上一次已提醒日期（不会包含 Token）
├── tests/                           # 离线模拟网页测试
├── requirements.txt                # Python 依赖列表
├── .gitignore                       # 不上传的文件
└── README.md
```

## 第 1 步：Windows 下载代码并配置 Python

将项目 ZIP 解压，比如放到 `D:\kpl-schedule-assistant`，用 VS Code 打开**包含 README.md 的项目根目录**。

按 `Win + R` 输入 `powershell`，在 PowerShell 中执行：

```powershell
cd D:\kpl-schedule-assistant
py --version
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
```

逐部分解释：

- `cd` = **change directory**，切换当前目录；后面是项目文件夹路径。若路径含空格，请加双引号。
- `py` 是 Windows Python 启动器；`--version` 输出版本。没有 `py` 时可改为 `python`。
- `-m` = **module**，按模块运行 Python 包。
- `pip` 是 Python 包管理工具，名称来自 “Pip Installs Packages”。
- `install -r requirements.txt` 从文件读取需要安装的第三方库；`-r` = **requirement**（依赖文件选项）。
- `unittest discover -s tests -v` 发现并运行 tests 中的测试；`-s` = **start directory**，`-v` = **verbose**（输出详细结果）。

看到 `Ran 5 tests ... OK` 代表本地模拟抓取和通知判断测试通过。注意测试不需要联网，不能证明线上网站目前仍可抓取。

## 第 2 步：尝试获取真实赛程

```powershell
py scripts\update_schedule.py
```

此命令请求 `https://wanplus.cn/kog/schedule`，找出比赛详情链接，再解析详情页的比赛**完整日期和北京时间**，生成 `docs/data/schedule.json`。

**正常日志示例**：

```text
[OK] 已更新 .../docs/data/schedule.json，共 N 场；今日 M 场
[INFO] 页面覆盖：2026-10-15, ...
```

如果出现 `[ERROR]`，可能是网络访问被限制、站点拒绝自动访问或网站结构发生变化。本项目不会把旧数据替换成虚假的空赛程；解决抓取问题前也不会发送微信通知。

## 第 3 步：本地打开网页

在项目根目录执行：

```powershell
py -m http.server 8000 --directory docs
```

- `http.server` 是 Python 内置 HTTP 文件服务模块；
- `8000` 是本地访问的端口号；
- `--directory docs` 指定网页文件来自 `docs` 文件夹，`--directory` 表示目录；
- 打开浏览器访问 <http://localhost:8000>，不要直接双击 `index.html`，因为网页需要读取同目录的数据文件。

运行时终端不要关闭；按 `Ctrl + C` 结束服务。

## 第 4 步：创建 GitHub 仓库并上传

先注册或登录 GitHub，安装 Git（如 `git --version` 能输出版本表示可用）。在 GitHub 网页右上角点 `+` → `New repository`：

- Repository name：`kpl-schedule-assistant`
- Visibility：建议 `Public`，GitHub Free 的 Pages 对公共仓库可用
- **不要勾选**初始 README、.gitignore、License（当前压缩包已自带 README 和 .gitignore）
- 点 `Create repository`，记下你的用户名

在项目根目录执行以下命令（把 `你的GitHub用户名` 换成真实用户名）：

```powershell
git init
git add .
git commit -m "feat: initial KPL assistant"
git branch -M main
git remote add origin https://github.com/你的GitHub用户名/kpl-schedule-assistant.git
git push -u origin main
```

解释：

- `git init` 初始化本地 Git 仓库；`init` 来自 **initialize**。
- `git add .` 将当前目录下文件加入待提交区域；`.` 代表当前目录。
- `git commit -m "..."` 提交快照；`-m` = **message**（本次提交说明）。
- `git branch -M main` 将当前分支命名为 main；`-M` 强制重命名分支。
- `git remote add origin URL` 配置远程仓库地址；`remote` 即远程，`origin` 是约定俗成的远程名称。
- `git push -u origin main` 将 main 分支上传到 origin；`-u` = **set-upstream**，建立以后同步所用的追踪关系。

第一次上传可能弹出浏览器让你授权 GitHub。如果提示需要设置 Git 身份，可执行 `git config --global user.name "昵称"` 和 `git config --global user.email "GitHub邮箱"` 后再 `git commit`。

## 第 5 步：开启 GitHub Pages

1. 进入仓库 `Settings` → `Pages`。
2. 在 `Build and deployment` 下，`Source` 选 **GitHub Actions**，不要选择 `Deploy from a branch`。
3. 进入仓库 `Actions`，选择左侧的 **更新并发布 KPL 赛程**，在右侧点击 `Run workflow`。
4. 选择分支 `main`；第一次运行把 `notify` 设为 `false`；点击运行。
5. 若抓取成功并部署成功，进入 `Settings → Pages` 查看网址。普通仓库网站通常是：`https://你的GitHub用户名.github.io/kpl-schedule-assistant/`。

> GitHub Actions 的 `schedule` 可能延迟；此项目在工作流中使用 `17 1 * * *`，即 **UTC 每天 01:17，北京时间每天 09:17**。GitHub 对不活跃的公共仓库，可能在 60 天后停用其定时工作流，届时需要在 Actions 页面重新启用。

### 如果工作流没有推送代码权限

仓库 `Settings` → `Actions` → `General` → `Workflow permissions`，如果可选，勾选 `Read and write permissions`，点击 `Save`。工作流文件本身也已明确申请 `contents: write`（写数据）、`pages: write` 和 `id-token: write`（部署所需）。

## 第 6 步：开启微信自动提醒（可选）

1. 打开 <https://www.pushplus.plus/> 登录，按平台要求完成必要账号验证/微信绑定。
2. 在个人中心获取自己的 Token。**不要把 Token 粘贴到代码、README 或仓库文件中。**
3. GitHub 仓库进入 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`。
4. `Name` 输入 **`PUSHPLUS_TOKEN`**（大小写一致）；`Secret` 输入个人 Token；点击 `Add secret`。
5. 第二天有 KPL 比赛且抓取成功、赛程覆盖当天时，工作流将在每天预定检查中调用 PushPlus 发送消息。
6. 若想立刻验证，可在 `Actions` → `Run workflow` 里将 `notify` 设为 `true` 再运行一次。**注意：这会真实推送当日赛程，测试时可能打扰你。**

行为：**无赛不发、过期数据不发、抓取失败不发、当天成功受理过一次的消息不重复发**。推送日期记录在 `data/notification_state.json`，自动随 Action 提交，防止误重复。PushPlus 返回成功代表接口已受理，不保证微信端必达。

## 第 7 步：装到手机桌面

- iPhone：Safari 打开网站 → 分享 → `添加到主屏幕`。
- Android：Chrome / Edge 打开网站 → 浏览器菜单 → `添加到主屏幕` 或 `安装应用`。
- 桌面 Chrome / Edge：地址栏右侧可能出现安装图标，点击即可安装。

PWA 不是原生 Android APK / iOS IPA，但能在支持的浏览器里以独立窗口打开。**自动微信通知来自 GitHub Actions + PushPlus，不依赖浏览器后台运行。**

## 故障排查

| 现象 | 怎么处理 |
|---|---|
| 页面“等待第一次抓取” | GitHub Actions 先手动运行一次；检查 `抓取最新赛程` 日志 |
| 网页显示旧数据 | 看最后更新时间，检查 Actions 是否成功，GitHub Pages 是否已部署 |
| Actions 中 `deploy-pages` 报错 | Settings → Pages → Source 必须选 GitHub Actions，且相关权限允许 |
| 没有微信提醒 | 检查 Token、PushPlus 账号绑定、今天是否有比赛、是否之前已发送、工作流是否执行 |
| 抓取失败 / 空赛程 | 赛事网站限制访问或页面改版，`抓取最新赛程` 日志会写原因；可运行本地离线测试排除代码基础问题 |
| 手机安装按钮缺失 | 用 HTTPS 的 Pages 网站打开，确认浏览器支持 PWA 安装；部分设备只支持“添加到主屏幕” |
| 屏幕上写“赛程尚未覆盖” | 数据源未给出所选日期，**不意味着那天没有 KPL 比赛** |

## 维护建议

- 每月关注一次 Github Actions 运行结果。赛程来源是网页结构，不保证永久稳定。
- 不建议高频率大规模抓取；当前工作流每日一次，以免给网站带来多余压力。
- 若要增加实时比分/开赛前 15 分钟提醒，建议换成合规稳定的实时数据 API，再单独开发调度器；不能拿当前每日工作流当成准实时提醒。
- GitHub Pages 是公共静态网页，不要把 Token 或私人信息放进 `docs/`。

## 参考资料

- [KPL 官网](https://kpl.qq.com/)
- [玩加电竞 KOG 赛程](https://wanplus.cn/kog/schedule)
- [GitHub Pages 工作流部署文档](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)
- [GitHub Actions 定时执行文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- [PushPlus 消息发送接口](https://www.pushplus.plus/doc/guide/api.html)
