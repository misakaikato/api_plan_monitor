#!/usr/bin/env python3
"""
API 服务 - 兼容 OpenRouter 格式的套餐查询接口
"""

import requests
import json
import datetime
import os
import sys
from fastapi import FastAPI

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

app = FastAPI(title="API Plan Monitor")


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
    "codex": {
        "name": "Codex (ChatGPT)",
        "api_url": "https://chatgpt.com/backend-api/wham/usage",
        "cookies_file": "cookies/codex_cookies.json",
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

    if "codex" in APP_CONFIG:
        cfg = APP_CONFIG["codex"]
        platforms["codex"].update({k: v for k, v in cfg.items() if v})

    # 添加解析函数
    platforms["minimax"]["parse_response"] = lambda data: parse_minimax(data)
    platforms["glm"]["parse_response"] = lambda data: parse_zhipu(data)
    platforms["codex"]["parse_response"] = lambda data: parse_codex(data)

    return platforms


PLATFORMS = get_platforms()


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

    for model in data.get("model_remains", []):
        model_name = model.get("model_name", "")
        if "M2.5" not in model_name:
            continue

        total_count = model.get("current_interval_total_count", 0)
        remains_count = model.get("current_interval_usage_count", 0)
        remains_time_ms = model.get("remains_time", 0)

        used_count = total_count - remains_count
        usage_percent = (used_count / total_count * 100) if total_count > 0 else 0

        remains_hours = remains_time_ms // (1000 * 60 * 60)
        remains_minutes = (remains_time_ms // (1000 * 60)) % 60

        start_time = model.get("start_time", 0)
        end_time = model.get("end_time", 0)
        start_dt = datetime.datetime.fromtimestamp(start_time / 1000) if start_time else None
        end_dt = datetime.datetime.fromtimestamp(end_time / 1000) if end_time else None

        # 计算剩余百分比
        remaining_percent = 100 - usage_percent

        return {
            "isValid": True,
            "is_active": True,
            "balance": remaining_percent,
            "remaining": remaining_percent,
            "unit": "USD",
            "planName": "MiniMax M2.5 套餐",
            "total": total_count,
            "used": used_count,
            "extra": f"周期: {start_dt.strftime('%H:%M') if start_dt else ''} - {end_dt.strftime('%H:%M') if end_dt else ''} (UTC+8), 已用{usage_percent:.0f}%, {remains_hours}小时{remains_minutes}分钟后重置"
        }

    return None


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
        percentage = limit.get("percentage", 0)
        next_reset = limit.get("nextResetTime", 0)

        if unit == 3:
            period_name = "每5小时"
        elif unit == 6:
            period_name = "每周"
        elif unit == 5:
            period_name = "每月"
        else:
            period_name = f"单位{unit}"

        reset_dt = datetime.datetime.fromtimestamp(next_reset / 1000) if next_reset else None
        reset_str = reset_dt.strftime("%m-%d %H:%M") if reset_dt else "N/A"

        result = {
            "type": period_name,
            "used_percent": f"{percentage}%",
            "reset_time": reset_str,
        }

        if limit_type == "TOKENS_LIMIT":
            result["limit_type"] = "TOKENS"
        elif limit_type == "TIME_LIMIT":
            result["limit_type"] = "MCP_TIME"
            result["total"] = limit.get("usage", 0)
            result["used"] = limit.get("currentValue", 0)
            result["remaining"] = limit.get("remaining", 0)

        results.append(result)

    # 合并所有限额信息到 extra
    extra_parts = []
    for r in results:
        extra_parts.append(f"{r['type']}: 已使用{r['used_percent']}, 重置 {r['reset_time']}")

    # 返回每周的已使用百分比作为主要 remaining
    weekly = next((r for r in results if r.get("type") == "每周"), None)

    return {
        "isValid": True,
        "is_active": True,
        "balance": 100 - int(weekly["used_percent"].replace("%", "")) if weekly else 0,
        "remaining": 100 - int(weekly["used_percent"].replace("%", "")) if weekly else 0,
        "unit": "USD",
        "planName": "智谱 AI 编程套餐",
        "used_percent": weekly["used_percent"] if weekly else "0%",
        "extra": "; ".join(extra_parts)
    }


def parse_codex(data):
    """解析 Codex (ChatGPT) API 响应"""
    if not data:
        return None

    rate_limit = data.get("rate_limit", {})
    code_review = data.get("code_review_rate_limit", {})
    credits = data.get("credits", {})

    # 5小时限额
    primary = rate_limit.get("primary_window", {})
    primary_used = primary.get("used_percent", 0)
    primary_remaining = 100 - primary_used

    # 每周限额
    secondary = rate_limit.get("secondary_window", {})
    secondary_used = secondary.get("used_percent", 0)
    secondary_remaining = 100 - secondary_used

    # 代码审查
    code_review_primary = code_review.get("primary_window", {})
    code_review_used = code_review_primary.get("used_percent", 0)
    code_review_remaining = 100 - code_review_used

    # 余额
    balance = credits.get("balance", "0")

    # 重置时间
    primary_reset = primary.get("reset_at", 0)
    secondary_reset = secondary.get("reset_at", 0)
    code_review_reset = code_review_primary.get("reset_at", 0)

    import datetime
    primary_reset_str = datetime.datetime.fromtimestamp(primary_reset).strftime("%m-%d %H:%M") if primary_reset else "N/A"
    secondary_reset_str = datetime.datetime.fromtimestamp(secondary_reset).strftime("%m-%d %H:%M") if secondary_reset else "N/A"
    code_review_reset_str = datetime.datetime.fromtimestamp(code_review_reset).strftime("%m-%d %H:%M") if code_review_reset else "N/A"

    extra_parts = [
        f"5小时限额: 已用{primary_used}%, 剩余{primary_remaining}%, 重置 {primary_reset_str}",
        f"每周限额: 已用{secondary_used}%, 剩余{secondary_remaining}%, 重置 {secondary_reset_str}",
        f"代码审查: 已用{code_review_used}%, 剩余{code_review_remaining}%, 重置 {code_review_reset_str}",
        f"余额: {balance}"
    ]

    return {
        "isValid": True,
        "is_active": True,
        "balance": secondary_remaining,
        "remaining": secondary_remaining,
        "unit": "USD",
        "planName": "Codex (ChatGPT) 套餐",
        "total": 100,
        "used": secondary_used,
        "extra": "; ".join(extra_parts)
    }


def fetch_plan_info(platform_key):
    """获取指定平台的套餐信息"""
    platform = PLATFORMS.get(platform_key)
    if not platform:
        return {"isValid": False, "invalidMessage": f"未知平台: {platform_key}"}

    cookies = load_cookies(platform_key)
    if not cookies:
        return {"isValid": False, "invalidMessage": f"未找到 {platform['name']} 的 cookies 文件"}

    api_url = platform["api_url"]
    if platform.get("group_id"):
        api_url = f"{api_url}?GroupId={platform['group_id']}"

    # 根据平台设置 headers
    if platform_key == "glm":
        auth_token = cookies.get("bigmodel_token_production", "")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://bigmodel.cn/usercenter/glm-coding/usage",
            "Origin": "https://bigmodel.cn",
        }
        if auth_token:
            headers["Authorization"] = auth_token
    elif platform_key == "codex":
        # Codex 需要 session token 作为 Bearer
        session_token = cookies.get("__Secure-next-auth.session-token", "")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://chatgpt.com/codex/settings/usage",
            "Origin": "https://chatgpt.com",
        }
        if session_token:
            headers["Authorization"] = f"Bearer {session_token}"
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
            # Codex 调试信息
            if platform_key == "codex":
                return {
                    "isValid": False,
                    "invalidMessage": f"请求失败: {response.status_code}",
                    "debug": {
                        "response_text": response.text[:500] if response.text else "empty"
                    }
                }
            return {"isValid": False, "invalidMessage": f"请求失败: {response.status_code}"}

        data = response.json()

        # 检查错误响应
        if data.get("base_resp", {}).get("status_code") not in (None, 0):
            error_msg = data.get("base_resp", {}).get("status_msg", "未知错误")
            return {"isValid": False, "invalidMessage": f"API 错误: {error_msg}"}
        if data.get("code") and data.get("code") != 200:
            error_msg = data.get("msg", "未知错误")
            return {"isValid": False, "invalidMessage": f"API 错误: {error_msg}"}

        # 解析响应
        parse_func = platform.get("parse_response")
        if parse_func:
            result = parse_func(data)
            return result

        return {"isValid": False, "invalidMessage": "解析失败"}

    except Exception as e:
        return {"isValid": False, "invalidMessage": f"请求异常: {str(e)}"}


# ============ API 路由 ============

@app.get("/minimax/user/balance")
def minimax_balance():
    """MiniMax 套餐余额查询"""
    return fetch_plan_info("minimax")


@app.get("/glm/user/balance")
def glm_balance():
    """智谱 AI 套餐余额查询"""
    return fetch_plan_info("glm")


@app.get("/codex/user/balance")
def codex_balance():
    """Codex (ChatGPT) 套餐余额查询"""
    return fetch_plan_info("codex")


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/")
def index():
    """API 概览"""
    return {
        "endpoints": {
            "/minimax/user/balance": "MiniMax 套餐余额",
            "/glm/user/balance": "智谱 AI 套餐余额",
            "/codex/user/balance": "Codex (ChatGPT) 套餐余额",
            "/health": "健康检查"
        }
    }


if __name__ == '__main__':
    import uvicorn

    print("=" * 60)
    print("API 服务启动")
    print("=" * 60)
    print("访问地址: http://localhost:8000")
    print("  /minimax/user/balance - MiniMax 套餐")
    print("  /glm/user/balance     - 智谱 AI 套餐")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=8000)
