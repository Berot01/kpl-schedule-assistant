"""当天赛程微信提醒；无比赛、过期、日期未覆盖、已发送均不推送。"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "docs" / "data" / "schedule.json"
STATE_PATH = ROOT / "data" / "notification_state.json"
TZ = ZoneInfo("Asia/Shanghai")
ENDPOINT = "https://www.pushplus.plus/send"


def decide(data: dict, state: dict, now: datetime):
    today = now.date().isoformat()
    if data.get("source") != "wanplus_schedule_and_match_details":
        return [], "赛程尚未同步成功"
    try:
        updated_at = datetime.fromisoformat(data["updated_at"])
    except (KeyError, TypeError, ValueError):
        return [], "缺失更新日期"
    if updated_at.tzinfo is None or abs((now - updated_at).total_seconds()) > 26 * 3600:
        return [], "赛程数据超过 26 小时，禁止发送"
    if today not in data.get("coverage_dates", []):
        return [], "数据未覆盖今天，禁止发送"
    if today in state.get("sent_dates", []):
        return [], "今天已经推送过"
    matches = [m for m in data.get("matches", []) if m.get("date") == today]
    if not matches:
        return [], "今天无 KPL 比赛，不发送通知"
    return matches, ""


def main() -> int:
    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        print("[SKIP] 未配置 PUSHPLUS_TOKEN；网页数据更新不受影响。")
        return 0
    now = datetime.now(TZ)
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {"sent_dates": []}
    matches, reason = decide(data, state, now)
    if not matches:
        print(f"[SKIP] {reason}")
        return 0
    today = now.date().isoformat()
    matches.sort(key=lambda m: m["time"])
    cards = []
    for item in matches:
        cards.append(f"""
        <div style="background:#ffffff;border:1px solid #eaeaea;border-radius:16px;padding:16px;margin:14px 0;">
            <div style="font-size:13px;color:#666;">{item['event']}</div>
            <div style="font-size:30px;font-weight:700;color:#ff6a3d;margin:10px 0 6px;">
                {item['time']}
            </div>
            <div style="font-size:20px;font-weight:700;color:#222;line-height:1.6;">
                {item['team_a']}
                <span style="font-size:14px;color:#999;padding:0 6px;">VS</span>
                {item['team_b']}
            </div>
            <div style="margin-top:14px;">
                <a href="{item['url']}"
                   style="display:inline-block;background:#1677ff;color:#fff;text-decoration:none;padding:8px 14px;border-radius:10px;font-size:14px;">
                   查看详情
                </a>
            </div>
        </div>
        """)

    html_content = f"""
    <div style="background:#f5f7fb;padding:20px;font-family:Arial,'Microsoft YaHei',sans-serif;">
        <div style="max-width:720px;margin:0 auto;background:#0f2747;color:#fff;border-radius:22px;padding:24px;">
            <div style="font-size:28px;font-weight:800;">KPL 今日赛程</div>
            <div style="font-size:14px;color:#d9e6ff;margin-top:8px;">
                日期：{today}（北京时间） · 共 {len(matches)} 场
            </div>

            <div style="margin-top:20px;">
                {''.join(cards)}
            </div>

            <div style="font-size:13px;color:#c7d3ea;margin-top:18px;line-height:1.7;">
                温馨提示：赛程可能临时调整，请以赛事官方信息为准。
            </div>
        </div>
    </div>
    """

    payload = {
        "token": token,
        "title": f"KPL 今日赛程 · {today} · {len(matches)} 场",
        "content": html_content,
        "template": "html",
        "channel": "wechat",
    }
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        if result.get("code") != 200:
            print(f"[ERROR] PushPlus 未接受消息：{result.get('msg', '未知错误')}", file=sys.stderr)
            return 1
    except (requests.RequestException, ValueError) as exc:
        print(f"[ERROR] 消息发送失败：{exc}", file=sys.stderr)
        return 1
    # 响应成功仅代表服务端受理，不保证微信端已最终送达。
    state["sent_dates"] = sorted(set(state.get("sent_dates", []) + [today]))[-45:]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[OK] PushPlus 已受理当日比赛通知，记入去重状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
