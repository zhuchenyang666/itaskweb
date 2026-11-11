# iTime 无终端版

把整个 iTime 文件夹复制到 Windows 64位主机的可写目录（例如D:/iTime），无需安装 Python、Node、npm、Nginx。

- 双击“启动工时服务.exe”：后台运行前端和接口，默认打开本机浏览器。
- 双击“关闭工时服务.exe”：通知本目录的服务正常退出，等待正在处理的请求完成。
- 关闭浏览器不会关闭服务。重复启动不会启动多个相同实例。
- 如果端口被其它软件占用，会弹出错误，不会结束其它软件。

## 目录必须一起保留

启动工时服务.exe：内置 Vue 页面、后端、Python 运行时和依赖。
关闭工时服务.exe：独立的关闭入口，和启动程序放在同一目录。
backend/resources/config.yaml：环境、数据库位置和EXE服务设置。
统计规则和任务类型存于账号数据库，通过管理员通用设置维护。
backend/下的配置数据目录：数据库，按年份分文件。
logs/：运行日志，首次启动后创建。

不要只复制EXE。不要将程序放到只读目录。
发布包默认使用 production，只复制打包时的正式数据库快照。mock 模拟数据库仅供源码本地测试。请妥善保管发布包，升级时保留目标主机上的数据库和配置。

## 端口

EXE版本由FastAPI同时提供前端静态页面和/api接口，默认统一使用5173端口。无须再运行Vite或单独启动8000端口。

server.desktop.listen-host：默认0.0.0.0，允许其它设备连接。
server.desktop.port：默认5173。
server.environments.local/production.browser-host：分别用于当前环境的启动提示和浏览器地址。服务监听地址由 desktop.listen-host 决定。
server.desktop.open-browser：默认true，启动成功后在运行 EXE 的电脑上打开浏览器。
server.environments中的port仍用于源码模式backend/run.py；EXE模式使用desktop.port。

若要在其他设备访问，请将 browser-host 配置为运行工时服务的主机地址，并使用对应地址和端口访问。
网络和防火墙必须允许访问5173，无需开放8000。

## 排错

启动失败查看当天的 logs/server_YYYYMMDD.log。控制台输出写入 logs/console_YYYYMMDD.log。日志按北京时间分日，跨天后自动写入新文件。

server.desktop.logs.cleanup-time：每天清理时间，使用北京时间和 HH:MM 格式，默认 "01:00"。
server.desktop.logs.retention-days：默认 7，删除日期早于当天减去该天数的日志。服务在清理时间之后启动时会补做清理。清理只处理上述带日期的日志。

无需启动监听的依赖检查可运行“启动工时服务.exe --check”，结果写入logs/check.json；检查包含历史候选接口，使用临时数据库，不改业务数据。

该版本手动启动，不注册系统服务，不设置开机自启。

## 重新打包

开发电脑运行 python build_all.py 即可重新构建。脚本会优先使用项目.venv，在 release 下生成新的 iTime-日期时间 目录，保留旧发布目录及其数据。服务主机仍无需开发环境。

升级服务器时，先关闭旧服务并备份数据，再替换两个 EXE。保留原来的数据库、日志和配置，按需合并新版本的配置项。确认新版运行正常后，可移除旧版外置的 frontend 和 _internal 目录。
