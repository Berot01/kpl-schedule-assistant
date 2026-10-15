"""从玩加电竞王者荣耀赛程与单场详情页生成静态赛程 JSON。

该站点并非承诺稳定的公开 API；仅请求公开网页，抓取失败时拒绝用空赛程覆盖旧数据。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "schedule.json"
SOURCE_URL = "https://wanplus.cn/kog/schedule"
TZ = ZoneInfo("Asia/Shanghai")
MATCH_URL_RE = re.compile(r"^/schedule/(\d{3,10})\.html$", re.I)
DATE_TIME_RE = re.compile(r"(?<!\d)(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\s+(\d{1,2}):(\d{2})(?!\d)")
MONTH_DAY_RE = re.compile(r"(?<!\d)(\d{1,2})[-/](\d{1,2})(?!\d)")
HEADLINE_RE = re.compile(r"(.+?)\s+(?:VS|vs|Vs)\s+(.+)$")


class SourceError(RuntimeError):
    pass


def http_get(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=(8, 20))
    response.raise_for_status()
    # requests normally decodes using the page-supplied charset
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_match_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    for a in soup.find_all("a", href=True):
        link = urljoin(SOURCE_URL, a["href"])
        parsed = urlparse(link)
        if parsed.hostname not in {"wanplus.cn", "www.wanplus.cn"}:
            continue
        if not MATCH_URL_RE.fullmatch(parsed.path):
            continue
        canonical = f"https://wanplus.cn{parsed.path}"
        if canonical not in found:
            found.append(canonical)
    return found


def guess_year(month: int, day: int, today: date) -> date:
    candidates = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        raise ValueError("日期不合法")
    return min(candidates, key=lambda item: abs((item - today).days))


def extract_coverage(html: str, today: date) -> list[str]:
    """仅从主赛程区日历附近的周日期确定页面覆盖日期，不能从场次推断无赛日。"""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    dates: set[date] = set()
    # 站点在日历导航中给出如 “周一 10-12” 和赛程标题 “10-15 今天”
    for pattern in (
        r"(?:周[一二三四五六日天])\s*(\d{1,2})-(\d{1,2})",
        r"(\d{1,2})-(\d{1,2})\s*(?:星期[一二三四五六日天]|今天)",
    ):
        for m in re.finditer(pattern, text):
            try:
                item = guess_year(int(m.group(1)), int(m.group(2)), today)
            except ValueError:
                continue
            if abs((item - today).days) <= 21:
                dates.add(item)
    # 若网站改版导致无法识别日历，拒绝声称当天“没有比赛”
    return [item.isoformat() for item in sorted(dates)]


def parse_match_detail(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    # 示例：2026 KPL年度总决赛-成都AG超玩会 VS 上海EDG.M比赛直播、视频、数据...
    head = re.split(r"比赛直播|比赛视频|比赛数据|_玩加| - 玩加", title, maxsplit=1)[0].strip()
    if not any(char in head for char in ("-", "－", "—")):
        return None
    # 使用第一个连接符切开赛事与双方队伍；战队名称可能包含“.”等字符。
    split = re.split(r"[-－—]", head, maxsplit=1)
    if len(split) != 2:
        return None
    competition, teams_text = [part.strip() for part in split]
    match = HEADLINE_RE.fullmatch(teams_text)
    if not match:
        return None
    team_a, team_b = (match.group(1).strip(), match.group(2).strip())
    if not team_a or not team_b or len(team_a) > 60 or len(team_b) > 60:
        return None
    body_text = soup.get_text(" ", strip=True)
    dt_match = DATE_TIME_RE.search(body_text)
    if not dt_match:
        raise SourceError(f"比赛详情无开赛时间：{url}")
    year, month, day, hour, minute = map(int, dt_match.groups())
    try:
        starts = datetime(year, month, day, hour, minute, tzinfo=TZ)
    except ValueError as exc:
        raise SourceError(f"比赛时间无效：{url}") from exc
    # 只按显式状态标注。其它情况统一视为赛程，不猜测实时结果。
    intro = body_text[: min(len(body_text), 520)]
    status = "live" if "正在进行" in intro else "scheduled"
    if re.search(r"比赛已结束|比赛结束|已完赛", intro):
        status = "finished"
    mid = re.search(r"/schedule/(\d+)\.html", url)
    return {
        "id": mid.group(1) if mid else f"{starts:%Y%m%d%H%M}-{team_a}-{team_b}",
        "date": starts.date().isoformat(),
        "time": starts.strftime("%H:%M"),
        "team_a": team_a,
        "team_b": team_b,
        "event": competition,
        "status": status,
        "url": url,
    }


def fetch_schedule(session: requests.Session, now: datetime, max_matches: int = 40) -> dict:
    page = http_get(session, SOURCE_URL)
    today = now.date()
    coverage = extract_coverage(page, today)
    urls = extract_match_urls(page)
    if not coverage:
        raise SourceError("未识别赛程页面日期范围，可能是页面结构变化")
    if len(urls) > max_matches:
        raise SourceError(f"单页出现 {len(urls)} 场链接，超过保护上限")
    if not urls:
        # 有明确日期范围但无场次，可正确表达“覆盖日期暂无比赛”。
        matches = []
    else:
        matches = []
        errors = []
        parsed_count = 0
        for index, url in enumerate(urls):
            try:
                item = parse_match_detail(http_get(session, url), url)
                if item:
                    parsed_count += 1
                    if "KPL" in item["event"].upper() and item["date"] in coverage:
                        matches.append(item)
            except (requests.RequestException, SourceError) as exc:
                errors.append(f"{url}: {exc}")
            if index + 1 < len(urls):
                time.sleep(0.15)
        # 单场抓取失败会导致漏报，因此禁止发布不完整数据。
        if errors:
            raise SourceError(f"{len(errors)} 场详情抓取失败。首条：{errors[0]}")
        if not parsed_count:
            raise SourceError("已找到比赛链接但所有比赛详情均解析失败，拒绝写入空数据")
    matches.sort(key=lambda m: (m["date"], m["time"], m["id"]))
    return {
        "schema_version": 1,
        "source": "wanplus_schedule_and_match_details",
        "source_url": SOURCE_URL,
        "timezone": "Asia/Shanghai",
        "updated_at": now.isoformat(timespec="seconds"),
        "coverage_dates": coverage,
        "matches": matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取 KPL 赛程并更新 docs/data/schedule.json")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="输出 JSON 路径")
    args = parser.parse_args()
    now = datetime.now(TZ)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; KPL-Daily-Assistant/1.0; personal-schedule-reader)",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        data = fetch_schedule(session, now)
    except (requests.RequestException, SourceError, ValueError) as exc:
        print(f"[ERROR] 数据抓取失败，保留上次成功的数据：{exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    today = now.date().isoformat()
    print(f"[OK] 已更新 {args.output}，共 {len(data['matches'])} 场；今日 {sum(m['date'] == today for m in data['matches'])} 场")
    print(f"[INFO] 页面覆盖：{', '.join(data['coverage_dates'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
