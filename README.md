# IPTV Collector

一个功能强大的 IPTV 直播源自动收集、过滤、检测与维护工具。

本项目旨在帮助用户从众多的订阅源中筛选出高质量、低延迟的有效直播源，并生成整洁的 M3U 播放列表。

## 直播源

* Github Actions 每天自动更新：

  直链：

       https://raw.githubusercontent.com/bjzhou/iptv-collector/output/iptv.m3u
  
       https://raw.githubusercontent.com/bjzhou/iptv-collector/output/iptv.txt
  
  代理：

       https://testingcf.jsdelivr.net/gh/bjzhou/iptv-collector@output/iptv.m3u
  
       https://testingcf.jsdelivr.net/gh/bjzhou/iptv-collector@output/iptv.txt

* 移动宽带不定期更新（含上海移动 IPV6 专属源）：

  直链：

       https://raw.githubusercontent.com/bjzhou/iptv-collector/output/iptv-cm.m3u
  
       https://raw.githubusercontent.com/bjzhou/iptv-collector/output/iptv-cm.txt
  
  代理：

       https://testingcf.jsdelivr.net/gh/bjzhou/iptv-collector@output/iptv-cm.m3u
  
       https://testingcf.jsdelivr.net/gh/bjzhou/iptv-collector@output/iptv-cm.txt


## ✨ 功能特点

*   **多格式支持**: 兼容 M3U 和 TXT 格式的直播源订阅链接。
*   **智能清洗 & 过滤**:
    *   **白名单机制**: 根据 `keywords.txt` 精确筛选目标频道，并按关键字顺序设定优先级。
    *   **黑名单机制**: 通过 `blacklist.txt` 剔除包含特定关键字的无效 URL。
*   **双重检测机制**:
    *   **极速初筛**: 利用 `asyncio` + `aiohttp` 进行高并发 HTTP 状态检查，快速剔除死链。
    *   **深度质检**: 调用 `FFmpeg` 对流媒体进行实际解码测试。
*   **智能排序策略**:
    1.  **优先级**: 按 `keywords.txt` 中的顺序优先排列。
    2.  **名称**: 按频道名称的自然顺序排列（例如 CCTV-1 在 CCTV-2 之前）。
    3.  **延迟**: 同类频道按延迟由低到高排列，确保最佳观看体验。
*   **自动化输出**: 生成标准 M3U 文件，内置 EPG 接口支持。

## 🛠️ 环境要求

*   **Python**: 3.12+
*   **包管理器**: 推荐使用 [uv](https://github.com/astral-sh/uv)
*   **FFmpeg**: 强烈推荐安装，用于精确的视频流有效性及延迟检测。

## 🚀 快速开始

### 1. 安装依赖

本项目使用 `uv` 进行包管理：

```bash
# 如果未安装 uv
pip install uv

# 同步项目依赖
uv sync
```

### 2. 配置文件

在项目根目录下创建或修改以下配置文件：

*   **`subscribe.txt`**: 订阅源列表文件。
    *   每行一个订阅源 URL（支持 .m3u 或 .txt 结尾的链接）。
*   **`keywords.txt`**: 频道白名单列表（决定收录哪些频道）。
    *   每行一个关键字（如 `CCTV`, `卫视`）。
    *   **注意**: 关键字的顺序决定了最终列表的频道分组排序。
*   **`blacklist.txt`** (可选): URL 黑名单。
    *   如果 URL 中包含文件中的任意关键字，该直播源将被丢弃。

### 3. 运行程序

```bash
# 使用 uv 运行
uv run main.py

# 或者直接使用 python (需确保环境已激活)
python main.py
```

### 4. 获取结果

运行完成后，程序将在当前目录下生成 **`iptv.m3u`** 文件。你可以将此文件导入到任意支持 M3U 的播放器（如 PotPlayer, VLC, Tivimate 等）中观看。

## 📂 项目结构

*   `main.py`: 程序入口，负责配置加载和任务调度。
*   `collector.py`: 核心功能库，包含下载、解析、并发检测等逻辑。
*   `iptv.m3u`: 生成的最终播放列表。

## ⚠️ 免责声明

本项目仅供技术学习与交流使用，请勿用于非法用途。项目中未提供任何直播源，所有源均需用户自行配置。
