"use strict";
const TIMEZONE = "Asia/Shanghai";
const REFRESH_LIMIT_MS = 26 * 60 * 60 * 1000;
const elements = {
  matches: document.getElementById("matches"),
  count: document.getElementById("match-count"),
  notice: document.getElementById("notice"),
  updated: document.getElementById("updated-text"),
  indicator: document.getElementById("sync-indicator"),
  refresh: document.getElementById("refresh"),
};
let schedule = null;
let selectedRange = "today";
let fetchError = false;

function isoBeijing(dayShift = 0) {
  const shifted = new Date(Date.now() + dayShift * 86400000);
  return new Intl.DateTimeFormat("en-CA", {timeZone: TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit"}).format(shifted);
}
function chineseDate(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12, 0));
  return new Intl.DateTimeFormat("zh-CN", {timeZone: "UTC", month: "long", day: "numeric", weekday: "short"}).format(date);
}
function node(tag, className, content) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (content !== undefined) el.textContent = content;
  return el;
}
function emptyState(symbol, title, detail) {
  const outer = node("div", "empty");
  outer.append(node("span", "empty-symbol", symbol), node("h3", "", title), node("p", "", detail));
  return outer;
}
function setNotice(text) {
  elements.notice.hidden = !text;
  elements.notice.textContent = text;
}
function freshness() {
  if (!schedule || !schedule.updated_at) return {ready:false, fresh:false, reason:"赛程尚未同步。请先在 GitHub Actions 手动运行一次“更新并发布 KPL 赛程”。"};
  const when = new Date(schedule.updated_at).getTime();
  if (!Number.isFinite(when)) return {ready:false, fresh:false, reason:"数据更新时间格式异常。"};
  if (Math.abs(Date.now() - when) > REFRESH_LIMIT_MS) return {ready:true, fresh:false, reason:"赛程数据已超过 26 小时未更新，展示内容可能过期。请检查 GitHub Actions 是否正常执行。"};
  if (fetchError) return {ready:true, fresh:false, reason:"最新数据获取失败，当前为离线缓存，仅供参考。"};
  return {ready:true, fresh:true, reason:""};
}
function getTargetDates() {
  const today = isoBeijing();
  if (selectedRange === "today") return [today];
  if (selectedRange === "tomorrow") return [isoBeijing(1)];
  return Array.from({length:7}, (_, i) => isoBeijing(i));
}
function refreshHead() {
  document.getElementById("date-today").textContent = chineseDate(isoBeijing());
  document.getElementById("date-tomorrow").textContent = chineseDate(isoBeijing(1));
  const check = freshness();
  elements.indicator.className = "tiny-dot" + (check.fresh ? " good" : " bad");
  elements.updated.textContent = schedule?.updated_at ? "更新于 " + new Intl.DateTimeFormat("zh-CN", {timeZone:TIMEZONE, month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(schedule.updated_at)) : "等待首次更新";
  setNotice(check.reason);
}
function createCard(match) {
  const card = node("article", "match-card");
  const side = node("div", "match-side");
  side.append(node("div", "match-date", chineseDate(match.date)), node("div", "match-time", match.time || "待定"));
  const detail = node("div", "match-detail");
  const meta = node("div", "match-meta");
  const currentMinutes = Date.now();
  const start = new Date(`${match.date}T${match.time || "00:00"}:00+08:00`).getTime();
  let status = match.status === "live" ? "正在进行*" : match.status === "finished" ? "已结束*" : "待开赛";
  let statusClass = match.status === "live" ? " live" : "";
  if (match.status === "scheduled" && currentMinutes > start) status = "已到开赛时间*";
  if (match.status === "scheduled" && currentMinutes <= start && start - currentMinutes < 60 * 60 * 1000) {status = "即将开始";statusClass=" soon";}
  meta.append(node("span", "status" + statusClass, status), node("span", "", "北京时间"));
  const teams = node("div", "match-teams");
  teams.append(node("span", "", match.team_a), node("span", "vs", "VS"), node("span", "", match.team_b));
  detail.append(meta, teams, node("div", "match-event", match.event || "KPL"));
  const link = node("a", "match-link", "赛事详情 ↗");
  try {
    const url = new URL(match.url);
    if (!['wanplus.cn','www.wanplus.cn'].includes(url.hostname) || url.protocol !== 'https:') throw new Error('unsafe URL');
    link.href = url.href;
  } catch (_) {link.href = "https://wanplus.cn/kog/schedule";}
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  card.append(side, detail, link);
  return card;
}
function render() {
  refreshHead();
  elements.matches.replaceChildren();
  const check = freshness();
  if (!check.ready) {
    elements.count.textContent = "--";
    elements.matches.append(emptyState("✧", "等待第一次抓取", "部署后请到 Actions 手动运行赛程同步。首次成功后才会显示真实比赛。"));
    return;
  }
  const dates = getTargetDates();
  const coverage = new Set(schedule.coverage_dates || []);
  const items = (schedule.matches || []).filter(m => dates.includes(m.date)).sort((a,b) => (a.date + a.time).localeCompare(b.date + b.time));
  elements.count.textContent = `${items.length} 场`;
  if (!items.length) {
    const completeCoverage = dates.every(d => coverage.has(d));
    elements.matches.append(completeCoverage
      ? emptyState("☾", "暂无 KPL 比赛", "所选日期在已同步的赛程范围内，暂未发现 KPL 对阵。")
      : emptyState("◇", "赛程尚未覆盖这些日期", "数据源还未提供所选日期的完整安排，并不代表一定没有比赛。"));
    return;
  }
  items.forEach(m => elements.matches.append(createCard(m)));
  const missing = dates.filter(d => !coverage.has(d));
  if (missing.length && selectedRange === "week") {
    elements.matches.append(emptyState("…", "部分日期尚未公布", "下方以外的日期仍需等待赛程页面更新。"));
  }
}
async function loadSchedule() {
  elements.refresh.disabled = true;
  try {
    const response = await fetch(`data/schedule.json?ts=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    if (result.schema_version !== 1 || !Array.isArray(result.matches) || !Array.isArray(result.coverage_dates)) throw new Error("JSON 格式不受支持");
    schedule = result;
    fetchError = false;
  } catch (error) {
    fetchError = true;
    if (!schedule) {setNotice("无法读取赛程文件，请确认已通过 HTTP 服务打开网页并完成部署。");}
  } finally {
    elements.refresh.disabled = false;
    render();
  }
}
document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => {
  selectedRange = button.dataset.range;
  document.querySelectorAll(".tab").forEach(tab => {
    const active = tab === button;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-pressed", String(active));
  });
  render();
}));
elements.refresh.addEventListener("click", loadSchedule);
loadSchedule();
if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
