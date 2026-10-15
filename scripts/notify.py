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
    lines = [f"{today} 今日有 {len(matches)} 场 KPL 比赛（北京时间）：", ""]
    for item in matches:
        lines.append(f"{item['time']}  {item['team_a']} VS {item['team_b']}")
        lines.append(f"{item['event']}")
        lines.append(item["url"])
        lines.append("")
    lines.append("赛程可能临时调整，以赛事官方信息为准。")
    payload = {
        "token": token,
        "title": f"KPL 今日赛程 · {today} · {len(matches)} 场",
        "content": "\n".join(lines),
        "template": "txt",
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
