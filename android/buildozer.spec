# =============================================================================
# MC互通管家 —— buildozer 打包配置
# 用法（在 android/ 目录下）：
#   1) 把核心库拷到本目录（CI 已自动做）：  cp -r ../mcbridge ./mcbridge
#   2) buildozer android debug
#   产物在 bin/ 目录下（.apk）
# =============================================================================

[app]

# 应用元信息
title = MC互通管家
package.name = mcbridge
package.domain = com.wjj481

# 版本号：与 mcbridge/__init__.py 保持一致
version = 1.0.0

# ---- 源码 ----
# 本目录（android/）就是打包源根目录；main.py 是入口。
# 核心库 mcbridge/ 需在打包前拷贝到本目录（见 README / CI）。
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,md,yml,yaml
# 排除缓存 / 构建产物
source.exclude_dirs = .buildozer,build,bin,__pycache__,tests

# ---- 依赖 ----
# python3 + kivy 是 GUI；其余为核心库运行所需（标准库 / 纯 python）。
requirements = python3, kivy
# 说明：
#   * 不打 Android 自带 Java 运行时——服务器端 JDK 由 Termux 的 openjdk-21 提供。
#   * 网络下载走标准库 urllib/requests 不在 requirements 里；
#     mcbridge 核心库用 urllib 即可（见 API_CONTRACT：User-Agent/超时/重试）。

# ---- 权限（AndroidManifest）----
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,\
    WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,\
    FOREGROUND_SERVICE_CONNECTED_SERVICE,WAKE_LOCK,CHANGE_WIFI_MULTICAST_STATE

# ---- 构建 ----
android.api = 34
android.minapi = 24
android.ndk = 25b
android.sdk = 34
android.archs = arm64-v8a
android.sdk_root =
android.ndk_dir =
android.accept_sdk_license = True

# 启动后保持屏幕常亮（挂机开服建议）
android.wakelock = True
# 前台服务：避免系统杀后台
android.foreground_service = True

# 全屏 / 方向
android.fullscreen = 0
android.orientation = portrait

# 图标（占位，CI 不强制；assets/ 里可放 icon.png）
# android.icon = %(source.dir)s/../assets/icon.png

# ---- 构建优化 ----
p4a.branch = master
p4a.debug = 0
# 不做 debuggable 发布包
android.debug_application = 0

# ---- 日志 ----
log_level = 2
# 保存 logcat 到文件
log_dir = ./.buildozer/logs

[buildozer]
# 并行与缓存
warn_on_root = 0
build_dir = ./.buildozer
# 使用系统已装的 SDK/NDK（CI 里由 setup-android 步骤提供）
android.sdk_path =
android.ndk_path =
