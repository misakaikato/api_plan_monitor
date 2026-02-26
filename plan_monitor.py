#!/usr/bin/env python3
"""
API 套餐用量监控工具
支持多种平台的 API 套餐查询
"""

import requests
import json
import datetime
import os
import sys

# 尝试导入 toml，失败则使用内置配置
try:
    import toml
    HAS_TOML = True
except ImportError:
    HAS_TOML = False

# 修复 Windows 控制台中文显示
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass


def load_config():
    """从 config.toml 加载配置"""
    config = {}
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")

    if os.path.exists(config_path) and HAS_TOML:
        try:
            config = toml.load(config_path)
            print(f"已从 config.toml 加载配置")
        except Exception as e:
            print(f"加载 config.toml 失败: {e}")

    return config


# 加载配置
APP_CONFIG = load_config()

# ============ 配置区域 ============

# 当前使用的平台: minimax / glm 等
CURRENT_PLATFORM = "minimax"

# ============ 平台配置 ============

# 默认配置
DEFAULT_PLATFORMS = {
    "minimax": {
        "name": "MiniMax",
        "api_url": "https://www.minimaxi.com/v1/api/openplatform/coding_plan/remains",
        "group_id": "",
        "cookies_file": "cookies/minimax_cookies.json",
        "model_filter": "M2.5",
    },
    "glm": {
        "name": "智谱 AI",
        "api_url": "https://bigmodel.cn/api/monitor/usage/quota/limit",
        "cookies_file": "cookies/zhipu_cookies.json",
    },
}


def get_platforms():
    """获取平台配置，优先使用 config.toml"""
    platforms = DEFAULT_PLATFORMS.copy()

    # 从配置覆盖
    if "minimax" in APP_CONFIG:
        cfg = APP_CONFIG["minimax"]
        platforms["minimax"].update({k: v for k, v in cfg.items() if v})

    if "glm" in APP_CONFIG:
        cfg = APP_CONFIG["glm"]
        platforms["glm"].update({k: v for k, v in cfg.items() if v})

    # 添加解析函数
    platforms["minimax"]["parse_response"] = lambda data: parse_minimax(data)
    platforms["glm"]["parse_response"] = lambda data: parse_zhipu(data)

    return platforms


PLATFORMS = get_platforms()
    },
    # 后续可添加其他平台:
    # "openai": {
    #     "name": "OpenAI",
    #     "api_url": "...",
    #     "cookies_file": "cookies/openai_cookies.json",
    #     "parse_response": lambda data: parse_openai(data),
    # },
}


def load_cookies(platform_key):
    """从 JSON 文件加载 cookies"""
    platform = PLATFORMS.get(platform_key)
    if not platform:
        return {}

    cookie_file = platform.get("cookies_file", "")
    if not cookie_file or not os.path.exists(cookie_file):
        return {}

    with open(cookie_file, 'r', encoding='utf-8') as f:
        cookie_data = json.load(f)

    cookies = {}

    # 支持多种 JSON 格式
    if isinstance(cookie_data, list):
        for item in cookie_data:
            if 'name' in item and 'value' in item:
                cookies[item['name']] = item['value']
            elif 'key' in item and 'value' in item:
                cookies[item['key']] = item['value']
    elif isinstance(cookie_data, dict):
        cookies = cookie_data

    return cookies


def parse_minimax(data):
    """解析 MiniMax API 响应"""
    if not data or "model_remains" not in data:
        return None

    results = []

    for model in data.get("model_remains", []):
        model_name = model.get("model_name", "Unknown")
        total_count = model.get("current_interval_total_count", 0)
        remains_count = model.get("current_interval_usage_count", 0)  # 实际是剩余
        remains_time_ms = model.get("remains_time", 0)

        used_count = total_count - remains_count
        usage_percent = (used_count / total_count * 100) if total_count > 0 else 0

        remains_hours = remains_time_ms // (1000 * 60 * 60)
        remains_minutes = (remains_time_ms // (1000 * 60)) % 60

        start_time = model.get("start_time", 0)
        end_time = model.get("end_time", 0)
        start_dt = datetime.datetime.fromtimestamp(start_time / 1000) if start_time else None
        end_dt = datetime.datetime.fromtimestamp(end_time / 1000) if end_time else None

        result = {
            "model": model_name,
            "period_start": start_dt.strftime("%H:%M") if start_dt else "N/A",
            "period_end": end_dt.strftime("%H:%M") if end_dt else "N/A",
            "total": total_count,
            "used": used_count,
            "remaining": remains_count,
            "remaining_percent": f"{usage_percent:.0f}%",
            "reset_time": f"{remains_hours}小时{remains_minutes}分钟后重置"
        }
        results.append(result)

    return results


def parse_zhipu(data):
    """解析智谱 AI API 响应"""
    if not data or "data" not in data:
        return None

    limits = data.get("data", {}).get("limits", [])
    if not limits:
        return None

    results = []

    for limit in limits:
        limit_type = limit.get("type", "")
        unit = limit.get("unit", 0)
        # percentage 是已使用百分比
        percentage = limit.get("percentage", 0)
        next_reset = limit.get("nextResetTime", 0)

        # 根据 unit 判断周期类型
        # unit: 3 = 每5小时, 6 = 每周, 5 = 每月
        if unit == 3:
            period_name = "每5小时"
        elif unit == 6:
            period_name = "每周"
        elif unit == 5:
            period_name = "每月"
        else:
            period_name = f"单位{unit}"

        # 解析重置时间
        reset_dt = datetime.datetime.fromtimestamp(next_reset / 1000) if next_reset else None
        reset_str = reset_dt.strftime("%m-%d %H:%M") if reset_dt else "N/A"

        # 获取配额和已使用 - percentage 是已使用百分比
        if limit_type == "TOKENS_LIMIT":
            total = limit.get("number", 0)
            # percentage 就是已使用百分比
            result = {
                "type": period_name,
                "total": total,
                "used_percent": f"{percentage}%",
                "reset_time": reset_str,
            }
        elif limit_type == "TIME_LIMIT":
            current = limit.get("currentValue", 0)
            remaining_time = limit.get("remaining", 0)
            total_time = current + remaining_time
            result = {
                "type": "MCP " + period_name,
                "total": total_time,
                "used": current,
                "remaining": remaining_time,
                "used_percent": f"{percentage}%",
                "reset_time": reset_str,
            }
        else:
            result = {
                "type": period_name,
                "used_percent": f"{percentage}%",
                "reset_time": reset_str,
            }

        results.append(result)

    return results


def fetch_plan_info(platform_key):
    """获取指定平台的套餐信息"""
    platform = PLATFORMS.get(platform_key)
    if not platform:
        print(f"未知平台: {platform_key}")
        return

    print(f"\n正在查询 {platform['name']} 套餐信息...")

    cookies = load_cookies(platform_key)
    if not cookies:
        print(f"未找到 {platform['name']} 的 cookies 文件")
        print(f"请在 {platform['cookies_file']} 中配置")
        return

    # 构建 API URL
    api_url = platform["api_url"]
    if platform.get("group_id"):
        api_url = f"{api_url}?GroupId={platform['group_id']}"

    # 根据平台设置 headers
    if platform_key == "glm":
        # 智谱需要从 cookie 中获取 authorization token
        auth_token = cookies.get("bigmodel_token_production", "")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://bigmodel.cn/usercenter/glm-coding/usage",
            "Origin": "https://bigmodel.cn",
        }
        if auth_token:
            headers["Authorization"] = auth_token
    else:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://platform.minimaxi.com/",
            "Origin": "https://platform.minimaxi.com",
        }

    try:
        response = requests.get(api_url, headers=headers, cookies=cookies, timeout=30)

        if response.status_code != 200:
            print(f"请求失败: {response.status_code}")
            print(response.text[:200])
            return

        data = response.json()

        # 检查错误响应 (通用 + 智谱格式)
        if data.get("base_resp", {}).get("status_code") not in (None, 0):
            error_msg = data.get("base_resp", {}).get("status_msg", "未知错误")
            print(f"API 错误: {error_msg}")
            return
        if data.get("code") and data.get("code") != 200:
            error_msg = data.get("msg", "未知错误")
            print(f"API 错误: {error_msg}")
            return

        # 解析响应
        parse_func = platform.get("parse_response")
        if parse_func:
            results = parse_func(data)

            # 选择特定模型
            model_filter = platform.get("model_filter", "")
            if model_filter:
                results = [r for r in results if model_filter in r.get("model", "")]

            # 如果没有匹配的，使用第一个
            if not results and platform.get("model_filter"):
                results = parse_func(data)[:1]

            if results:
                print(f"\n{'=' * 60}")
                print(f"{platform['name']} 套餐信息")
                if model_filter and platform_key != "glm":
                    print(f"(显示: {model_filter})")
                print('=' * 60)

                # 根据平台选择输出格式
                if platform_key == "glm":
                    for item in results:
                        print(f"\n【{item['type']}】")
                        print(f"  已使用: {item['used_percent']}")
                        if "used" in item:
                            print(f"  已用: {item['used']} / {item['total']}")
                            print(f"  剩余: {item['remaining']}")
                        print(f"  重置时间: {item['reset_time']}")
                else:
                    for item in results:
                        print(f"\n【{item['model']}】")
                        print(f"  时间周期: {item['period_start']} - {item['period_end']} (UTC+8)")
                        print(f"  当前使用: {item['used']} / {item['total']}")
                        print(f"  剩余: {item['remaining']} ({item['remaining_percent']})")
                        print(f"  重置时间: {item['reset_time']}")
            else:
                print("未找到匹配的模型数据")

    except Exception as e:
        print(f"请求异常: {e}")


def list_platforms():
    """列出所有可用的平台"""
    print("\n支持的平台:")
    for key, platform in PLATFORMS.items():
        marker = " ← 当前" if key == CURRENT_PLATFORM else ""
        print(f"  - {key}: {platform['name']}{marker}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="API 套餐用量监控工具")
    parser.add_argument("-p", "--platform", default=CURRENT_PLATFORM, help="选择平台")
    parser.add_argument("-l", "--list", action="store_true", help="列出所有可用平台")
    parser.add_argument("-a", "--all", action="store_true", help="查询所有平台")

    args = parser.parse_args()

    print("=" * 60)
    print("API 套餐用量监控工具")
    print("=" * 60)

    if args.list:
        list_platforms()
        return

    if args.all:
        for platform_key in PLATFORMS.keys():
            fetch_plan_info(platform_key)
            print()
    else:
        fetch_plan_info(args.platform)


if __name__ == "__main__":
    main()
