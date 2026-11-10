# iTime 工时管理

iTime 使用 Vue、FastAPI、SQLAlchemy 和 SQLite，支持工时填报、人员管理和年度工作饱和度统计。员工只查看自己的工时。管理员可查看全员工时、管理账号和任务类型，以及导出年度 XLSX。

## 本地运行

需要 Python 3.12 和 Node.js。以下命令在 Windows PowerShell 中执行。

在项目根目录准备后端：

~~~powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
Copy-Item backend/resources/config.example.yaml backend/resources/config.yaml
$env:ITIME_ENV = "local"
.venv/Scripts/python.exe backend/seed_mock.py
.venv/Scripts/python.exe backend/run.py
~~~

已有本地配置时，保留原来的 config.yaml。模拟数据是可选的，跳过 seed_mock.py 即可从空库开始。

另开一个终端启动前端：

~~~powershell
cd frontend
npm ci
npm run dev
~~~

浏览器访问 [http://127.0.0.1:5173](http://127.0.0.1:5173)。Vite 会将 /api 转发至本机 8000 端口。首次建库会创建 admin，初始密码为 123456。模拟员工账号见 backend/mock/人员账号清单.csv，初始密码也是 123456。正式使用前请修改管理员初始密码。

## 功能

- 登录和返回首页时显示加载动画。会话在北京时间次日零点失效，也可主动退出。
- 新增和编辑工时支持主题日历。所属项目、任务描述和备注按填报人的历史内容提供候选，输入文字可匹配候选的任意位置。没有匹配项时不展开列表。
- 工时记录和用户管理支持每页 10、20、30、40、50 或 100 条，默认 20 条，可跳转到指定页。工时记录支持日期、关键词和停用人员筛选。
- 管理员可创建、停用、重新启用员工和重置密码。停用后保留历史工时，并撤销该账号的登录会话。
- 管理员总览和年度 XLSX 共用统计口径。年度导出按所选年份和停用人员开关生成，月份、日期、关键词和分页只影响当前列表。管理员自身不计入统计。年假计入实际工时和饱和度，不计入项目投入与有效代码行。

## 配置和数据

环境由 backend/resources/config.yaml 的 server.active 决定，可用 ITIME_ENV 覆盖。未创建本地配置时使用仓库中的 config.example.yaml。默认数据位置如下。

| 环境 | 账号库 | 2026 年工时库 |
| --- | --- | --- |
| local | backend/mock/accounts.sqlite3 | backend/mock/2026/worktime.sqlite3 |
| production | backend/real/accounts.sqlite3 | backend/real/2026/worktime.sqlite3 |

账号和通用设置存于账号库，工时按年存储。备份时先停服并复制整个数据目录，或使用 SQLite 备份接口。切换环境不会复制数据。

仓库使用匿名模拟员工。若需保留自己的测试名单，可在 backend/mock/roster.csv 写入无表头的 CSV，每行为“姓名、旧账号前缀、现账号”。实际数据库、名单、本机配置、日志和发布包均不提交到 Git。

- seed_mock.py --replace 会先备份本地模拟库，再替换模拟人员和工时。
- seed_mock.py --rebalance 会先备份，再调整带模拟标记的工时。
- migrate_accounts.py 可根据本地名单迁移旧账号，保留用户 ID 并备份账号库。

## Windows EXE

在项目根目录执行：

~~~powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements-build.txt
.venv/Scripts/python.exe build_all.py
~~~

每次构建在 release 下生成独立的时间戳目录。启动工时服务.exe 内置前端、后端和运行依赖，关闭工时服务.exe 独立。配置和数据库在 backend，日志在 logs。发布版默认使用 production，只复制正式数据库。

升级时先停服，替换同批次的两个 EXE，保留服务器数据库和配置。EXE 使用 server.desktop 配置，默认监听 5173 端口。启动时打开的地址由 browser-host 决定。日志按北京时间分日，默认每天 01:00 清理超过 7 天的日志。详见 [Windows 发布说明](PACKAGING.md)。

## 测试

~~~powershell
cd backend
../.venv/Scripts/python.exe -m unittest discover -s tests -v
cd ../frontend
node tests/table.test.js
node tests/toast.test.js
npm run build
~~~

后端测试使用临时数据库，无需启动服务。
