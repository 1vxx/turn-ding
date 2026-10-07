<p align="center">
  <img src="assets/icon.svg" width="96" height="96" alt="turn-ding">
</p>

<h1 align="center">turn-ding</h1>

<p align="center"><a href="README.md">English</a> · <b>简体中文</b></p>

一个 Claude Code 插件：Claude 干完活就响一声，你可以放心去做别的事。

把一个耗时的任务交给 Claude，切去做别的，十分钟后回来才发现它九分钟前就做完了。turn-ding 解决的就是这件事：Claude 一结束，你就能听到。如果你正在听歌或看视频，它会把那些声音暂时调低，让提示音透出来，响完再调回去。

仅支持 macOS。

## 你会听到什么

| 发生了什么 | 声音 |
| --- | --- |
| Claude 回答完了 | *Glass* 响三下 |
| 这一轮因为出错而中断 | *Basso* 响三下 |
| 你自己打断了 Claude | 不响 |
| 子代理（subagent）完成 | 不响，只有主对话会响 |

两种声音故意做得不一样：隔着房间也能听出来，是该回去看结果，还是该回去处理问题。

## 安装

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

没有配置文件。可调的值写在 [hooks/register.ts](hooks/register.ts) 的最上面，所以要改它们，需要从你自己的仓库副本安装。

### 从自己的副本安装

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
| `REPEAT` | `3` | 响几下 |
| `RING_SECONDS` | `0.5` | 每一下响多久（秒） |
| `DUCK_GAIN` | `0.4` | 响的时候其他应用保留多少音量。`0` 是静音，`1` 是不变 |
| `FALLBACK_VOLUME` | `4` | 无法调低其他声音时，提示音放大多少倍。`1` 是原始音量 |

想换声音，就把同一个文件里的 `Glass` 和 `Basso` 换成 `/System/Library/Sounds` 下的其他名字。看看有哪些可选：

```bash
ls /System/Library/Sounds
```

```bash
afplay /System/Library/Sounds/Hero.aiff
```

## 常见问题

**什么都听不到。**
先确认 Mac 没有静音，输出设备选对了。再用 `claude plugin list` 确认插件已安装并启用，然后新开一个会话。如果 turn-ding 完全无法播放，它会在 Claude Code 里显示一条以 `turn-ding:` 开头的提示，说明原因。

**会响，但我的音乐没有变小。**
负责调低其他声音的助手程序没跑起来，turn-ding 退回了普通播放。在 Intel Mac 上这是预期行为，按[从自己的副本安装](#从自己的副本安装)编译一次即可。

**太响了 / 太轻了。**
提示音跟随系统音量。想改变其他应用被调低的程度，调整 `DUCK_GAIN`。

**每个子代理完成都会响吗？**
不会。只有主对话会响，所以一个任务即使分给十个子代理，也只在最后响一次。

**万一出问题，我的音乐会一直很小声吗？**
不会。助手程序在结束时会恢复音量，中途被杀掉时也会先恢复。

**支持 Linux 或 Windows 吗？**
暂时不支持。它依赖 macOS 的系统音效和音频接口。

## 工作原理

turn-ding 监听 Claude Code 的 `turn.complete` 事件。主对话的一轮结束时，它运行一个 Swift 小程序（[helper/turn-ding.swift](helper/turn-ding.swift)），请 macOS 的混音器把其他所有应用的音量调低，播放提示音，再调回去。其他应用的声音只是被按比例缩小，不会被暂停，所以起伏很平滑。

它用到的混音器接口 `AudioDeviceDuck` 由 CoreAudio 导出，但不在公开头文件里，未来的 macOS 版本可能会改动它。一旦调用失败，turn-ding 会退回到 `afplay`，改为把提示音放大播放。提示音总归会响。

## 参与开发

```
.claude-plugin/plugin.json   插件清单
.claude-plugin/marketplace.json   让 `claude plugin install` 能找到它
hooks/hooks.json             声明 hooks 模块
hooks/register.ts            插件本体
hooks/register.test.ts       测试
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

改了 Swift 源码后重新编译：

```bash
sh helper/build.sh
```

欢迎提 issue 和 pull request。
