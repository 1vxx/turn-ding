<p align="center">
  <img src="assets/icon.svg" width="96" height="96" alt="turn-ding">
</p>

<h1 align="center">turn-ding</h1>

<p align="center"><a href="README.md">English</a> · <b>简体中文</b></p>

一个支持 Claude Code 和 Codex 的插件：一轮干完就响，你可以放心去做别的事。

把一个耗时的任务交给编程代理，切去做别的，十分钟后回来才发现它九分钟前就做完了。turn-ding 解决的就是这件事：一轮结束，你就能听到。如果你正在听歌或看视频，它会把那些声音暂时调低，让提示音透出来，响完再调回去。

仅支持 macOS。

## 你会听到什么

| 发生了什么 | 声音 |
| --- | --- |
| Claude Code 或 Codex 回答完了 | *Glass* 响三下 |
| Claude Code 这一轮因为出错而中断 | *Basso* 响三下 |
| 代理停下来等你：弹出选项让你选，或者请求运行某个工具的权限 | *Ping* 响一下 |
| 你自己打断了代理 | 不响 |
| 子代理（subagent）完成 | 不响，只有主对话会响 |

三种声音故意做得不一样：隔着房间也能听出来，是该回去看结果、回去处理问题，还是只需要过去点一下。

两种接入都会根据你的状态调整：正在前台看着会话时，不到十秒的任务完成不响，较长的任务只响一下，也不压低其他声音。锁屏或三分钟没有操作后，会进一步压低其他声音，并每分钟补响一下，最多五次。恢复操作或开始新一轮时停止重复提醒。

Codex 当前的[生命周期 hooks](https://learn.chatgpt.com/docs/hooks) 没有提供整轮失败事件，所以单独的 *Basso* 报错提示目前只支持 Claude Code。某个工具执行失败不等于整轮任务失败。

## 安装

### Codex

需要 macOS、Python 3.9 或更新版本（PATH 中能找到 `python3`），以及支持插件和生命周期 hooks 的较新版本 Codex。支持本地 CLI 和桌面会话。每个 hook 都会启动一次 `python3`，所以它最好直接指向真实的解释器：pyenv 这类版本管理器的 shim 会让每次调用多花 100 毫秒以上。

从自己的仓库副本安装：

```bash
git clone https://github.com/1vxx/turn-ding.git ~/turn-ding
codex plugin marketplace add ~/turn-ding
codex plugin add turn-ding@turn-ding
```

重启 Codex，审阅并信任 turn-ding 的 hooks。CLI 中使用 `/hooks`，桌面应用中使用 hook 审阅界面。插件启用后，未信任的 hooks 仍会被 Codex 跳过。也需要启用 hooks（`features.hooks` 不能是 `false`）。

这些改动发布到 GitHub 后，可以用 `codex plugin marketplace add 1vxx/turn-ding` 代替添加本地目录。本地安装后，修改或拉取仓库更新时，再运行一次 `codex plugin add turn-ding@turn-ding` 并重启 Codex；如果提示 hooks 已改变，重新审阅。

卸载：

```bash
codex plugin remove turn-ding@turn-ding
```

云端任务无法通过这些本地命令 hooks 在你的 Mac 上播放声音。

### Claude Code

需要 macOS 和较新版本的 [Claude Code](https://claude.com/claude-code)。

```bash
claude plugin marketplace add 1vxx/turn-ding
```

```bash
claude plugin install turn-ding@turn-ding
```

这样就装好了。新开一个 Claude Code 会话，随便问一句话，回答完时你应该能听到三声提示音。之后每个会话都生效，终端和桌面应用都一样。

以后更新：

```bash
claude plugin update turn-ding@turn-ding
```

卸载：

```bash
claude plugin uninstall turn-ding@turn-ding
```

### 只想先试试？

克隆下来，只在一次会话里加载，什么都不安装：

```bash
git clone https://github.com/1vxx/turn-ding.git ~/turn-ding
```

```bash
claude --plugin-dir ~/turn-ding
```

### Intel 芯片的 Mac

仓库自带的助手程序是为 Apple Silicon 编译的。没有它 turn-ding 也能响，只是没法调低其他声音，会改为把提示音本身放大。想要完整效果，就从自己的副本安装并在那里编译助手程序（需要先装 Xcode 命令行工具），见[从自己的副本安装](#从自己的副本安装)。

## 按自己的喜好调整

没有配置文件。Claude Code 的可调值写在 [hooks/register.ts](hooks/register.ts) 的最上面，Codex 的写在 [hooks/codex.py](hooks/codex.py) 的最上面，所以要改它们，需要从你自己的仓库副本安装。如果两种接入都用，保持两处的值一致。

### 从自己的副本安装

Codex 使用上面的 [Codex 安装步骤](#codex)。以下步骤适用于 Claude Code。

```bash
git clone https://github.com/1vxx/turn-ding.git ~/turn-ding
```

```bash
sh ~/turn-ding/helper/build.sh
```

```bash
claude plugin marketplace add ~/turn-ding
```

```bash
claude plugin install turn-ding@turn-ding
```

编译这一步只在 Intel Mac 上、或者改了 Swift 源码之后才需要。如果之前已经从 GitHub 安装过，先运行 `claude plugin uninstall turn-ding@turn-ding` 和 `claude plugin marketplace remove turn-ding`。

这样安装后，Claude Code 直接读取 `~/turn-ding` 这个目录。改完文件，在会话里运行 `/reload-plugins`，改动就生效了。

### 可以改什么

| 值 | 默认 | 作用 |
| --- | --- | --- |
| `REPEAT` | `3` | 一轮结束时响几下 |
| `ASK_REPEAT` | `1` | 代理停下来等你时响几下 |
| `RING_SECONDS` | `0.5` | 每一下响多久（秒） |
| `DUCK_GAIN` | `0.4` | 响的时候其他应用保留多少音量。`0` 是静音，`1` 是不变 |
| `FALLBACK_VOLUME` | `4` | 无法调低其他声音时，提示音放大多少倍。`1` 是原始音量 |
| `WATCHING_SECONDS` | `60` | 前台会话最近有操作时，视为正在观看的时间窗口 |
| `AWAY_SECONDS` | `180` | 多久没有操作后视为离开；锁屏也算离开 |
| `QUICK_TURN_MS` | `10000` | 正在观看时，短于这个时长的任务完成不响 |
| `AWAY_DUCK_GAIN` | `0.2` | 离开时其他应用保留多少音量 |
| `REMIND_TIMES` | `5` | 离开时最多补响几次 |

重复提醒的间隔在 Claude Code 中是 `REMIND_EVERY_MS = 60000`，在 Codex 中是 `REMIND_EVERY_SECONDS = 60`。

想换声音，就把对应接入文件里的 `Glass` 和 `Ping`，或 Claude Code 文件里的 `Basso`，换成 `/System/Library/Sounds` 下的其他名字。看看有哪些可选：

```bash
ls /System/Library/Sounds
```

```bash
afplay /System/Library/Sounds/Hero.aiff
```

## 常见问题

**什么都听不到。**
先确认 Mac 没有静音，输出设备选对了。再用 `claude plugin list` 确认插件已安装并启用，然后新开一个会话。如果 turn-ding 完全无法播放，它会在 Claude Code 里显示一条以 `turn-ding:` 开头的提示，说明原因。

Codex 中用 `codex plugin list --marketplace turn-ding --json` 检查插件，审阅 hooks，并确认 Codex 环境中 `python3 --version` 能正常运行。前台短任务完成不响是预期行为。后台播放失败会写入插件的 `PLUGIN_DATA/codex` 目录中的 `notifications.log`；没有插件数据目录时，写入 `$TMPDIR/turn-ding-<uid>/codex`。

**会响，但我的音乐没有变小。**
负责调低其他声音的助手程序没跑起来，turn-ding 退回了普通播放。在 Intel Mac 上这是预期行为，按[从自己的副本安装](#从自己的副本安装)编译一次即可。

**太响了 / 太轻了。**
提示音跟随系统音量。想改变其他应用被调低的程度，调整 `DUCK_GAIN`。

**每个子代理完成都会响吗？**
完成时不会。一轮结束的提示音只有主对话才响，所以一个任务即使分给十个子代理，也只在最后响一次。但子代理停下来等你操作时会响，因为它确实在等你。

**万一出问题，我的音乐会一直很小声吗？**
不会。助手程序在结束时会恢复音量，中途被杀掉时也会先恢复。

**支持 Linux 或 Windows 吗？**
暂时不支持。它依赖 macOS 的系统音效和音频接口。

## 工作原理

turn-ding 监听 Claude Code 的 `turn.complete` 事件。主对话的一轮结束时，它运行一个 Swift 小程序（[helper/turn-ding.swift](helper/turn-ding.swift)），请 macOS 的混音器把其他所有应用的音量调低，播放提示音，再调回去。其他应用的声音只是被按比例缩小，不会被暂停，所以起伏很平滑。

Codex 使用独立的原生插件清单和[命令 hook 配置](hooks/codex.json)。`Stop` 负责主对话完成提示，`PreToolUse` 负责提问提示，`PermissionRequest` 负责审批提示。`UserPromptSubmit`、`PostToolUse`、`Interrupt` 和 `SessionEnd` 在工作恢复或结束时取消重复提醒。Python 接入层启动有次数限制的后台播放进程，调用同一个 Swift 助手；hooks 返回 JSON，不改变工具权限。会话计时和取消标记保存在仓库外，不保存提问或对话记录。

它用到的混音器接口 `AudioDeviceDuck` 由 CoreAudio 导出，但不在公开头文件里，未来的 macOS 版本可能会改动它。一旦调用失败，turn-ding 会退回到 `afplay`，改为把提示音放大播放。提示音总归会响。

## 参与开发

```
.claude-plugin/plugin.json   插件清单
.claude-plugin/marketplace.json   让 `claude plugin install` 能找到它
.codex-plugin/plugin.json    Codex 清单，选择独立的命令 hooks
hooks/hooks.json             声明 hooks 模块
hooks/register.ts            插件本体
hooks/register.test.ts       测试
hooks/codex.json             Codex 生命周期 hooks
hooks/codex.py               Codex 接入和后台播放进程
hooks/codex_test.py          Codex 测试，仅使用 Python 标准库
helper/turn-ding.swift       音频助手程序的源码
helper/build.sh              编译出 bin/turn-ding
bin/turn-ding                编译好的助手程序（arm64）
```

检查插件并运行测试：

```bash
claude plugin validate .
```

```bash
claude plugin test .
```

测试 Codex 接入，不会实际播放声音：

```bash
python3 -m unittest discover -s hooks -p codex_test.py -v
```

改了 Swift 源码后重新编译：

```bash
sh helper/build.sh
```

欢迎提 issue 和 pull request。

## 许可证

[MIT](LICENSE)
