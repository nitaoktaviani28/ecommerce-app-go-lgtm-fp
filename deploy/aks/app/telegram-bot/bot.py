import os
import json
import logging
import httpx
from datetime import datetime, timezone, timedelta
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://grafana.monitoring.svc.cluster.local")
GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY", "")
GRAFANA_USERNAME = os.environ.get("GRAFANA_USERNAME", "")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki-gateway.monitoring.svc.cluster.local")
MIMIR_URL = os.environ.get("MIMIR_URL", "http://mimir-gateway.monitoring.svc.cluster.local")
TEMPO_URL = os.environ.get("TEMPO_URL", "http://tempo-query-frontend.monitoring.svc.cluster.local:3200")
BEDROCK_PROXY_URL = os.environ.get("BEDROCK_PROXY_URL", "http://bedrock-proxy.ecommerce.svc.cluster.local:4000")
ALLOWED_CHAT_IDS = os.environ.get("ALLOWED_CHAT_IDS", "").split(",")

# Services list
SERVICES = ["api-gateway", "product-service", "order-service", "user-service", "payment-service", "frontend"]

# WIB timezone
WIB = timezone(timedelta(hours=7))


def _grafana_headers() -> dict:
    """Build Grafana auth headers when API key is configured."""
    return {"Authorization": f"Bearer {GRAFANA_API_KEY}"} if GRAFANA_API_KEY else {}


def _grafana_basic_auth() -> tuple[str, str] | None:
    """Return basic auth tuple when username/password is configured."""
    if GRAFANA_USERNAME and GRAFANA_PASSWORD:
        return (GRAFANA_USERNAME, GRAFANA_PASSWORD)
    return None


async def _grafana_get(client: httpx.AsyncClient, path: str, params: dict | None = None) -> httpx.Response:
    """Try Grafana Bearer auth first, then fallback to Basic on 401."""
    resp = await client.get(
        f"{GRAFANA_URL}{path}",
        params=params,
        headers=_grafana_headers(),
    )

    basic_auth = _grafana_basic_auth()
    if resp.status_code == 401 and basic_auth:
        resp = await client.get(
            f"{GRAFANA_URL}{path}",
            params=params,
            auth=basic_auth,
        )

    return resp


def _is_firing_state(state: str) -> bool:
    """Normalize alert state checks across Grafana/Prometheus payloads."""
    return (state or "").strip().lower() in {"active", "firing", "alerting"}


def _normalize_alert(raw: dict) -> dict:
    """Normalize alert payloads from different Grafana endpoints."""
    labels = raw.get("labels", {}) or {}
    annotations = raw.get("annotations", {}) or {}
    status = raw.get("status", {})

    # Alertmanager v2 uses status.state, Prometheus-style uses top-level state.
    state = raw.get("state") or (status.get("state") if isinstance(status, dict) else "") or "unknown"

    return {
        "alertname": labels.get("alertname", "N/A"),
        "severity": labels.get("severity", "unknown"),
        "summary": annotations.get("summary") or annotations.get("description") or "N/A",
        "state": state,
        "starts_at": raw.get("startsAt") or raw.get("activeAt") or "",
    }


async def _get_grafana_alerts() -> tuple[list[dict], list[str]]:
    """Fetch alerts from multiple Grafana APIs to support different deployments."""
    errors = []
    normalized_alerts = []

    endpoints = [
        {
            "path": "/api/alertmanager/grafana/api/v2/alerts",
            "extract": lambda payload: payload if isinstance(payload, list) else [],
        },
        {
            "path": "/api/prometheus/grafana/api/v1/alerts",
            "extract": lambda payload: payload.get("data", {}).get("alerts", []) if isinstance(payload, dict) else [],
        },
    ]

    async with httpx.AsyncClient(timeout=10) as client:
        for ep in endpoints:
            try:
                resp = await _grafana_get(client, ep["path"])
            except Exception as exc:
                errors.append(f"{ep['path']}: network error ({str(exc)[:80]})")
                continue

            if resp.status_code != 200:
                errors.append(f"{ep['path']}: HTTP {resp.status_code}")
                continue

            try:
                payload = resp.json()
            except Exception:
                errors.append(f"{ep['path']}: invalid JSON response")
                continue

            raw_alerts = ep["extract"](payload)
            normalized_alerts.extend(_normalize_alert(a) for a in raw_alerts if isinstance(a, dict))

    return normalized_alerts, errors


def is_authorized(update: Update) -> bool:
    """Check if chat is authorized."""
    if not ALLOWED_CHAT_IDS or ALLOWED_CHAT_IDS == [""]:
        return True  # No restriction if not configured
    return str(update.effective_chat.id) in ALLOWED_CHAT_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with available commands."""
    if not is_authorized(update):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    text = """🤖 <b>LGTM Ops Bot - E-Commerce Monitoring</b>

Halo! Aku bot untuk monitoring e-commerce app (LGTM Stack).

<b>📋 Available Commands:</b>

<b>🔍 Status & Health</b>
/health - Health check semua services
/alerts - Alert yang sedang firing
/alert_history - Riwayat alert 24 jam terakhir

<b>📊 Metrics</b>
/cpu - CPU usage per service
/memory - Memory usage per service
/latency - HTTP latency P95/P99
/traffic - Request rate per service
/error - Detail error + contoh log error terbaru
/errors - HTTP error rate (4xx/5xx)

<b>📝 Logs</b>
/logs - Recent logs semua service
/logs &lt;service&gt; - Recent logs per service
/logs_error &lt;service&gt; - Error logs
/logs_all &lt;service&gt; - All recent logs

<b>🔗 Traces</b>
/traces &lt;service&gt; - Recent slow traces
/trace &lt;trace_id&gt; - Detail trace by ID

<b>🧠 AI Assistant</b>
/incident - AI incident summary (current alerts)
/diagnose &lt;service&gt; - AI diagnosis untuk service
/ask &lt;question&gt; - Tanya AI tentang infra/app

<b>📖 Playbook</b>
/playbook - List semua playbook
/playbook_cpu - Playbook: High CPU
/playbook_memory - Playbook: High Memory
/playbook_restart - Playbook: Pod Restart Loop
/playbook_5xx - Playbook: High 5xx Errors
/playbook_latency - Playbook: High Latency
/playbook_disk - Playbook: Disk Full
/playbook_notraffic - Playbook: No Traffic

<b>⚙️ Infra</b>
/nodes - Node status & resource usage
/pods - Pod status di namespace ecommerce
/deployments - Deployment status

Ketik command atau tanya langsung! 💬"""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ==================== STATUS & HEALTH ====================

async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Health check all service endpoints."""
    if not is_authorized(update):
        return

    await update.message.reply_text("⏳ Running health checks...")

    endpoints = {
        "api-gateway": "http://api-gateway.ecommerce.svc.cluster.local:8080/health",
        "product-service": "http://product-service.ecommerce.svc.cluster.local:8080/health",
        "order-service": "http://order-service.ecommerce.svc.cluster.local:8080/health",
        "user-service": "http://user-service.ecommerce.svc.cluster.local:8080/health",
        "payment-service": "http://payment-service.ecommerce.svc.cluster.local:8080/health",
        "bedrock-proxy": "http://bedrock-proxy.ecommerce.svc.cluster.local:4000/health",
    }

    text = "🏥 <b>Health Check Results</b>\n\n"

    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in endpoints.items():
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    text += f"🟢 <code>{name}</code>: OK ({resp.elapsed.total_seconds()*1000:.0f}ms)\n"
                else:
                    text += f"🟡 <code>{name}</code>: HTTP {resp.status_code}\n"
            except Exception:
                text += f"🔴 <code>{name}</code>: UNREACHABLE\n"

    text += f"\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show currently firing alerts."""
    if not is_authorized(update):
        return

    try:
        alerts_data, errors = await _get_grafana_alerts()

        if not alerts_data and errors:
            err_text = "\n".join(errors[:3])
            await update.message.reply_text(
                "❌ <b>Gagal ambil data alert dari Grafana.</b>\n"
                f"Detail: <code>{err_text}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        if not alerts_data:
            await update.message.reply_text("✅ <b>Tidak ada alert yang firing saat ini.</b>", parse_mode=ParseMode.HTML)
            return

        firing = [a for a in alerts_data if _is_firing_state(a.get("state", ""))]

        if not firing:
            await update.message.reply_text("✅ <b>Semua alert resolved.</b>", parse_mode=ParseMode.HTML)
            return

        text = f"🚨 <b>{len(firing)} Alert(s) Firing</b>\n\n"
        for a in firing[:10]:  # Max 10
            severity = a.get("severity", "unknown")
            sev_icon = "🔴" if severity == "critical" else "🟡"
            text += (
                f"{sev_icon} <b>{a.get('alertname', 'N/A')}</b>\n"
                f"   Severity: {severity}\n"
                f"   State: {a.get('state', 'unknown')}\n"
                f"   Summary: {a.get('summary', 'N/A')}\n\n"
            )

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def alert_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show alert history in last 24 hours."""
    if not is_authorized(update):
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Query annotation (alert state history) from Grafana.
            now = datetime.now(timezone.utc)
            from_ts = int((now - timedelta(hours=24)).timestamp() * 1000)
            to_ts = int(now.timestamp() * 1000)

            ann_resp = await _grafana_get(
                client,
                "/api/annotations",
                params={"from": from_ts, "to": to_ts, "type": "alert", "limit": 20},
            )
            annotations = ann_resp.json() if ann_resp.status_code == 200 else []

            # Fallback for setups where annotation history is disabled or empty.
            if not annotations:
                prom_resp = await _grafana_get(client, "/api/prometheus/grafana/api/v1/alerts")
                prom_payload = prom_resp.json() if prom_resp.status_code == 200 else {}
                current_alerts = prom_payload.get("data", {}).get("alerts", [])
            else:
                current_alerts = []

        if not annotations:
            if not current_alerts:
                await update.message.reply_text("📜 Tidak ada alert history dalam 24 jam terakhir.")
                return

            normalized_current = [_normalize_alert(a) for a in current_alerts if isinstance(a, dict)]
            firing_now = [a for a in normalized_current if _is_firing_state(a.get("state", ""))]

            if not firing_now:
                await update.message.reply_text(
                    "📜 History annotation kosong, dan tidak ada alert aktif saat ini."
                )
                return

            text = "📜 <b>Alert Snapshot (fallback saat history tidak tersedia)</b>\n\n"
            for a in firing_now[:15]:
                sev_icon = "🔴" if a.get("severity", "").lower() == "critical" else "🟡"
                text += f"{sev_icon} <code>{a.get('alertname', 'N/A')}</code> → {a.get('state', 'unknown')}\n"

            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            return

        text = "📜 <b>Alert History (24 jam)</b>\n\n"
        for ann in annotations[:15]:
            alert_name = ann.get("alertName", "N/A")
            state = ann.get("newState", "unknown")
            time_str = datetime.fromtimestamp(ann.get("time", 0) / 1000, WIB).strftime("%H:%M WIB")
            state_icon = "🔴" if state == "alerting" else "✅"
            text += f"{state_icon} <code>{time_str}</code> {alert_name} → {state}\n"

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


# ==================== METRICS ====================

async def _query_mimir(query: str, tenant: str = "pods") -> dict:
    """Query Mimir/Prometheus with tenant header."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{MIMIR_URL}/prometheus/api/v1/query",
            params={"query": query},
            headers={"X-Scope-OrgID": tenant},
        )
        return resp.json() if resp.status_code == 200 else {}


async def cpu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show CPU usage per container in ecommerce namespace."""
    if not is_authorized(update):
        return

    data = await _query_mimir(
        'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="ecommerce", container!=""}[5m])) * 100'
    )
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("⚠️ No CPU data available.")
        return

    text = "🖥️ <b>CPU Usage (ecommerce namespace)</b>\n\n"
    sorted_results = sorted(results, key=lambda x: float(x["value"][1]), reverse=True)

    for r in sorted_results[:15]:
        pod = r["metric"].get("pod", "unknown")
        value = float(r["value"][1])
        bar = "█" * int(value / 10) + "░" * (10 - int(value / 10))
        icon = "🔴" if value > 80 else "🟡" if value > 50 else "🟢"
        text += f"{icon} <code>{pod[:30]}</code>\n   {bar} {value:.1f}%\n"

    text += f"\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show memory usage per container."""
    if not is_authorized(update):
        return

    data = await _query_mimir(
        'sum by (pod) (container_memory_working_set_bytes{namespace="ecommerce", container!=""}) / 1024 / 1024'
    )
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("⚠️ No memory data available.")
        return

    text = "💾 <b>Memory Usage (ecommerce namespace)</b>\n\n"
    sorted_results = sorted(results, key=lambda x: float(x["value"][1]), reverse=True)

    for r in sorted_results[:15]:
        pod = r["metric"].get("pod", "unknown")
        value = float(r["value"][1])
        text += f"📦 <code>{pod[:30]}</code>: {value:.0f} MiB\n"

    text += f"\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def latency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show P95 HTTP latency per service."""
    if not is_authorized(update):
        return

    data = await _query_mimir(
        'histogram_quantile(0.95, sum by (le, job) (rate(http_server_duration_milliseconds_bucket[5m])))'
    )
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("⚠️ No latency data available.")
        return

    text = "⏱️ <b>HTTP Latency P95</b>\n\n"
    for r in results:
        job = r["metric"].get("job", "unknown")
        value = float(r["value"][1])
        icon = "🔴" if value > 1000 else "🟡" if value > 500 else "🟢"
        text += f"{icon} <code>{job}</code>: {value:.0f}ms\n"

    text += f"\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def traffic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show request rate per service."""
    if not is_authorized(update):
        return

    data = await _query_mimir(
        'sum by (job) (rate(http_server_duration_milliseconds_count[5m]))'
    )
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("⚠️ No traffic data available.")
        return

    text = "🌐 <b>Request Rate (req/sec)</b>\n\n"
    for r in results:
        job = r["metric"].get("job", "unknown")
        value = float(r["value"][1])
        text += f"📈 <code>{job}</code>: {value:.2f} req/s\n"

    text += f"\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show HTTP error rate (4xx/5xx)."""
    if not is_authorized(update):
        return

    data = await _query_mimir(
        'sum by (job, http_status_code) (rate(http_server_duration_milliseconds_count{http_status_code=~"[4-5].."}[5m]))'
    )
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("✅ <b>Tidak ada HTTP errors saat ini.</b>", parse_mode=ParseMode.HTML)
        return

    text = "❌ <b>HTTP Error Rate (4xx/5xx)</b>\n\n"
    for r in results:
        job = r["metric"].get("job", "unknown")
        code = r["metric"].get("http_status_code", "?")
        value = float(r["value"][1])
        text += f"🔴 <code>{job}</code> [{code}]: {value:.3f} req/s\n"

    text += f"\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ==================== LOGS ====================

async def _query_loki(query: str, limit: int = 20) -> list:
    """Query Loki for near-real-time logs."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params={
                "query": query,
                "limit": limit,
                "direction": "backward",
                "start": int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp() * 1e9),
                "end": int(datetime.now(timezone.utc).timestamp() * 1e9),
            }
        )
        data = resp.json() if resp.status_code == 200 else {}

    results = data.get("data", {}).get("result", [])
    logs = []
    for stream in results:
        for value in stream.get("values", []):
            logs.append(value[1])
    return logs[:limit]


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get recent general logs (all levels), optionally filtered by service."""
    if not is_authorized(update):
        return

    service = context.args[0] if context.args else ""
    target = service if service else "semua service"
    await update.message.reply_text(f"⏳ Fetching recent logs untuk {target}...")

    if service:
        query = f'{{namespace="ecommerce", pod=~"{service}.*"}}'
    else:
        query = '{namespace="ecommerce"}'

    log_entries = await _query_loki(query, limit=10)

    if not log_entries:
        if service:
            await update.message.reply_text(
                f"✅ Tidak ada logs terbaru untuk <code>{service}</code> (5 menit terakhir).",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text("✅ Tidak ada logs terbaru (5 menit terakhir).", parse_mode=ParseMode.HTML)
        return

    text = f"📝 <b>Recent Logs: {target}</b> (5 menit terakhir)\n\n"
    for i, entry in enumerate(log_entries[:10], 1):
        # Truncate long log lines
        truncated = entry[:150] + "..." if len(entry) > 150 else entry
        text += f"<code>{i}. {truncated}</code>\n\n"

    await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)


async def logs_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get error-level logs."""
    if not is_authorized(update):
        return
    service = context.args[0] if context.args else ""
    if not service:
        await update.message.reply_text(f"ℹ️ Usage: /logs_error &lt;service&gt;\nServices: {', '.join(SERVICES)}", parse_mode=ParseMode.HTML)
        return

    query = f'{{namespace="ecommerce", pod=~"{service}.*"}} | logfmt | level=~"error|fatal|panic"'
    log_entries = await _query_loki(query, limit=15)

    if not log_entries:
        await update.message.reply_text(
            f"✅ No error/fatal logs for <code>{service}</code> (5 menit terakhir).",
            parse_mode=ParseMode.HTML,
        )
        return

    text = f"🔴 <b>Error/Fatal Logs: {service}</b> (5 menit terakhir)\n\n"
    for entry in log_entries[:10]:
        text += f"<code>{entry[:150]}</code>\n\n"

    await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)


async def logs_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get all recent logs."""
    if not is_authorized(update):
        return
    service = context.args[0] if context.args else ""
    if not service:
        await update.message.reply_text(f"ℹ️ Usage: /logs_all &lt;service&gt;\nServices: {', '.join(SERVICES)}", parse_mode=ParseMode.HTML)
        return

    query = f'{{namespace="ecommerce", pod=~"{service}.*"}}'
    log_entries = await _query_loki(query, limit=15)

    if not log_entries:
        await update.message.reply_text(
            f"⚠️ No logs for <code>{service}</code> (5 menit terakhir).",
            parse_mode=ParseMode.HTML,
        )
        return

    text = f"📋 <b>Recent Logs: {service}</b> (5 menit terakhir)\n\n"
    for entry in log_entries[:10]:
        text += f"<code>{entry[:150]}</code>\n\n"

    await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)


async def error_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current HTTP errors and the latest related error logs."""
    if not is_authorized(update):
        return

    data = await _query_mimir(
        'sum by (job, http_status_code) (rate(http_server_duration_milliseconds_count{http_status_code=~"[4-5].."}[5m]))'
    )
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("✅ <b>Tidak ada HTTP error saat ini.</b>", parse_mode=ParseMode.HTML)
        return

    sorted_results = sorted(results, key=lambda x: float(x["value"][1]), reverse=True)

    text = "❌ <b>Current HTTP Errors + Why</b>\n\n"
    top = sorted_results[0]
    top_job = top["metric"].get("job", "unknown")
    top_code = top["metric"].get("http_status_code", "?")
    top_rate = float(top["value"][1])

    text += "<b>Top error saat ini:</b>\n"
    text += f"🔴 <code>{top_job}</code> [{top_code}] {top_rate:.3f} req/s\n\n"
    text += "<b>Ringkasan error rate:</b>\n"

    for r in sorted_results[:8]:
        job = r["metric"].get("job", "unknown")
        code = r["metric"].get("http_status_code", "?")
        value = float(r["value"][1])
        text += f"• <code>{job}</code> [{code}] {value:.3f} req/s\n"

    # Try to infer service name used in pod labels, then fetch latest error logs.
    service_guess = top_job.replace("-service", "")
    query = f'{{namespace="ecommerce", pod=~"{service_guess}.*"}} |~ "(?i)error|exception|panic|timeout|failed|404|500"'
    log_entries = await _query_loki(query, limit=5)

    if log_entries:
        text += "\n<b>Contoh log error terbaru:</b>\n"
        for i, entry in enumerate(log_entries, 1):
            text += f"<code>{i}. {entry[:160]}</code>\n"
    else:
        text += "\nℹ️ Belum ada baris log error yang match dalam 5 menit terakhir."

    text += f"\n\n🕐 <i>{datetime.now(WIB).strftime('%d %b %Y %H:%M WIB')}</i>"
    await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)


# ==================== TRACES ====================

async def traces(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get recent slow traces for a service."""
    if not is_authorized(update):
        return

    service = context.args[0] if context.args else ""
    if not service:
        await update.message.reply_text(f"ℹ️ Usage: /traces &lt;service&gt;\nServices: {', '.join(SERVICES)}", parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text(f"⏳ Searching slow traces for {service}...")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{TEMPO_URL}/api/search",
                params={
                    "q": f'{{ resource.service.name = "{service}" && duration > 1s }}',
                    "limit": 5,
                    "start": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
                    "end": int(datetime.now(timezone.utc).timestamp()),
                }
            )
            data = resp.json() if resp.status_code == 200 else {}

        traces_data = data.get("traces", [])
        if not traces_data:
            await update.message.reply_text(f"✅ No slow traces (>1s) for <code>{service}</code>.", parse_mode=ParseMode.HTML)
            return

        text = f"🔗 <b>Slow Traces: {service}</b> (&gt;1s, 1 jam terakhir)\n\n"
        for t in traces_data[:5]:
            trace_id = t.get("traceID", "?")
            duration_ms = t.get("durationMs", 0)
            root_name = t.get("rootServiceName", "?")
            text += (
                f"🔸 <code>{trace_id[:16]}...</code>\n"
                f"   Duration: {duration_ms}ms | Root: {root_name}\n\n"
            )

        text += "💡 Gunakan /trace &lt;trace_id&gt; untuk detail."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def trace_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get trace detail by ID."""
    if not is_authorized(update):
        return

    trace_id = context.args[0] if context.args else ""
    if not trace_id:
        await update.message.reply_text("ℹ️ Usage: /trace &lt;trace_id&gt;", parse_mode=ParseMode.HTML)
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TEMPO_URL}/api/traces/{trace_id}")
            data = resp.json() if resp.status_code == 200 else {}

        if not data:
            await update.message.reply_text(f"⚠️ Trace <code>{trace_id}</code> not found.", parse_mode=ParseMode.HTML)
            return

        batches = data.get("batches", [])
        text = f"🔗 <b>Trace Detail</b>\n<code>{trace_id}</code>\n\n"

        span_count = 0
        for batch in batches:
            resource = batch.get("resource", {})
            service_name = "unknown"
            for attr in resource.get("attributes", []):
                if attr.get("key") == "service.name":
                    service_name = attr.get("value", {}).get("stringValue", "unknown")

            scope_spans = batch.get("scopeSpans", [])
            for ss in scope_spans:
                for span in ss.get("spans", []):
                    span_count += 1
                    if span_count <= 10:
                        name = span.get("name", "?")
                        status = span.get("status", {}).get("code", "OK")
                        text += f"  {'🔴' if status == 'ERROR' else '🟢'} <code>{service_name}</code> → {name}\n"

        text += f"\n📊 Total spans: {span_count}"
        await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


# ==================== AI ASSISTANT ====================

async def incident(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate AI incident summary from current alerts."""
    if not is_authorized(update):
        return

    await update.message.reply_text("🧠 Generating AI incident summary...")

    try:
        # Get current alerts
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await _grafana_get(client, "/api/alertmanager/grafana/api/v2/alerts")
            alerts_data = resp.json() if resp.status_code == 200 else []

        firing = [a for a in alerts_data if a.get("status", {}).get("state") == "active"]

        if not firing:
            await update.message.reply_text("✅ Tidak ada incident aktif saat ini.")
            return

        # Format alerts for AI
        alert_text = ""
        for a in firing:
            labels = a.get("labels", {})
            annotations = a.get("annotations", {})
            alert_text += f"- {labels.get('alertname')}: {annotations.get('summary', 'N/A')}\n"

        # Call Bedrock AI
        prompt = f"""Kamu adalah SRE assistant. Berikan incident summary singkat dalam Bahasa Indonesia.

Alerts yang sedang firing:
{alert_text}

Format:
1. Ringkasan situasi (1-2 kalimat)
2. Impact yang mungkin terjadi
3. Recommended action (langkah konkrit)

Jawab singkat dan actionable."""

        async with httpx.AsyncClient(timeout=30) as client:
            ai_resp = await client.post(
                f"{BEDROCK_PROXY_URL}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": prompt}]},
            )
            ai_data = ai_resp.json()
            summary = ai_data.get("choices", [{}])[0].get("message", {}).get("content", "AI unavailable")

        text = f"🧠 <b>AI Incident Summary</b>\n\n{summary}"
        await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI diagnosis for a specific service."""
    if not is_authorized(update):
        return

    service = context.args[0] if context.args else ""
    if not service:
        await update.message.reply_text(f"ℹ️ Usage: /diagnose &lt;service&gt;\nServices: {', '.join(SERVICES)}", parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text(f"🧠 Diagnosing {service}...")

    try:
        # Gather metrics
        cpu_data = await _query_mimir(f'sum(rate(container_cpu_usage_seconds_total{{namespace="ecommerce", pod=~"{service}.*"}}[5m])) * 100')
        mem_data = await _query_mimir(f'sum(container_memory_working_set_bytes{{namespace="ecommerce", pod=~"{service}.*"}}) / 1024 / 1024')
        
        # Get recent error logs
        error_logs = await _query_loki(f'{{namespace="ecommerce", pod=~"{service}.*"}} |~ "(?i)error"', limit=5)

        cpu_val = "N/A"
        mem_val = "N/A"
        if cpu_data.get("data", {}).get("result"):
            cpu_val = f"{float(cpu_data['data']['result'][0]['value'][1]):.1f}%"
        if mem_data.get("data", {}).get("result"):
            mem_val = f"{float(mem_data['data']['result'][0]['value'][1]):.0f} MiB"

        logs_text = "\n".join(error_logs[:5]) if error_logs else "No recent errors"

        prompt = f"""Kamu adalah SRE assistant. Diagnosa service berikut dalam Bahasa Indonesia.

Service: {service}
CPU Usage: {cpu_val}
Memory Usage: {mem_val}
Recent Error Logs:
{logs_text[:500]}

Berikan:
1. Status assessment (healthy/degraded/critical)
2. Potential issues yang terdeteksi
3. Recommended actions

Singkat dan jelas."""

        async with httpx.AsyncClient(timeout=30) as client:
            ai_resp = await client.post(
                f"{BEDROCK_PROXY_URL}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": prompt}]},
            )
            ai_data = ai_resp.json()
            diagnosis = ai_data.get("choices", [{}])[0].get("message", {}).get("content", "AI unavailable")

        text = f"🧠 <b>AI Diagnosis: {service}</b>\n\n{diagnosis}"
        await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask AI anything about the infrastructure."""
    if not is_authorized(update):
        return

    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text("ℹ️ Usage: /ask &lt;pertanyaan&gt;", parse_mode=ParseMode.HTML)
        return

    await update.message.reply_text("🧠 Thinking...")

    prompt = f"""Kamu adalah SRE/DevOps assistant untuk e-commerce app yang berjalan di AKS dengan LGTM stack (Loki, Grafana, Tempo, Mimir).

Services: api-gateway, product-service, order-service, user-service, payment-service, frontend
Stack: Go backend, Vue.js frontend, Grafana LGTM observability, AKS Kubernetes

Pertanyaan: {question}

Jawab dalam Bahasa Indonesia, singkat dan actionable."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            ai_resp = await client.post(
                f"{BEDROCK_PROXY_URL}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": prompt}]},
            )
            ai_data = ai_resp.json()
            answer = ai_data.get("choices", [{}])[0].get("message", {}).get("content", "AI unavailable")

        await update.message.reply_text(f"🧠 {answer}"[:4000], parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


# ==================== PLAYBOOK ====================

PLAYBOOKS = {
    "cpu": {
        "title": "🔥 Playbook: High CPU Usage",
        "steps": """<b>Trigger:</b> CPU usage &gt; 85% for 5+ minutes

<b>Diagnosis Steps:</b>
1. Cek pod mana yang high CPU:
   <code>kubectl top pods -n ecommerce --sort-by=cpu</code>

2. Cek apakah ada spike traffic:
   <code>/traffic</code> (bot command)

3. Cek logs untuk loop/goroutine leak:
   <code>/logs &lt;service&gt;</code>

<b>Remediation:</b>
1. <b>Short-term:</b> Scale up replicas
   <code>kubectl scale deploy &lt;service&gt; -n ecommerce --replicas=3</code>

2. <b>Medium-term:</b> Cek apakah ada inefficient code (N+1 query, infinite loop)

3. <b>Long-term:</b> Setup HPA (Horizontal Pod Autoscaler)
   <code>kubectl autoscale deploy &lt;service&gt; -n ecommerce --min=2 --max=5 --cpu-percent=70</code>

<b>Escalation:</b> Jika tidak resolve dalam 15 menit → escalate ke Tech Lead""",
    },
    "memory": {
        "title": "💾 Playbook: High Memory Usage",
        "steps": """<b>Trigger:</b> Memory usage &gt; 85% of limit

<b>Diagnosis Steps:</b>
1. Cek memory per pod:
   <code>kubectl top pods -n ecommerce --sort-by=memory</code>

2. Cek apakah ada OOMKilled:
   <code>kubectl get pods -n ecommerce -o wide | grep OOM</code>

3. Cek memory trend (apakah memory leak):
   <code>/memory</code> (bot command)

<b>Remediation:</b>
1. <b>Short-term:</b> Restart pod yang leak
   <code>kubectl rollout restart deploy &lt;service&gt; -n ecommerce</code>

2. <b>Medium-term:</b> Increase memory limit
   Edit deployment resources.limits.memory

3. <b>Long-term:</b> Profile dengan pprof/Pyroscope untuk find leak
   Cek Pyroscope dashboard di Grafana

<b>Escalation:</b> Jika OOMKilled berulang → escalate ke Backend Team""",
    },
    "restart": {
        "title": "🔄 Playbook: Pod Restart Loop",
        "steps": """<b>Trigger:</b> Pod restart &gt; 3x dalam 10 menit

<b>Diagnosis Steps:</b>
1. Cek pod status:
   <code>kubectl get pods -n ecommerce</code>
   <code>kubectl describe pod &lt;pod-name&gt; -n ecommerce</code>

2. Cek crash logs:
   <code>kubectl logs &lt;pod-name&gt; -n ecommerce --previous</code>

3. Cek events:
   <code>kubectl get events -n ecommerce --sort-by=.lastTimestamp</code>

<b>Common Causes:</b>
• OOMKilled → increase memory limit
• CrashLoopBackOff → fix application error
• Liveness probe failed → fix health endpoint / increase timeout
• Image pull error → check image registry

<b>Remediation:</b>
1. Jika config error → fix configmap/secret lalu rollout
2. Jika code error → rollback:
   <code>kubectl rollout undo deploy &lt;service&gt; -n ecommerce</code>
3. Jika resource issue → scale resources

<b>Escalation:</b> Immediately jika production impact → escalate ke On-Call Engineer""",
    },
    "5xx": {
        "title": "🚨 Playbook: High 5xx Error Rate",
        "steps": """<b>Trigger:</b> HTTP 5xx rate &gt; threshold

<b>Diagnosis Steps:</b>
1. Cek error rate per service:
   <code>/errors</code> (bot command)

2. Cek error logs:
   <code>/logs_error &lt;service&gt;</code>

3. Cek traces untuk failed requests:
   <code>/traces &lt;service&gt;</code>

4. Cek apakah downstream service down:
   <code>/health</code>

<b>Common Causes:</b>
• Database connection timeout
• Downstream service unavailable
• Memory/CPU exhaustion
• Bad deployment (new bug)

<b>Remediation:</b>
1. <b>Jika bad deploy:</b> Rollback immediately
   <code>kubectl rollout undo deploy &lt;service&gt; -n ecommerce</code>

2. <b>Jika DB issue:</b> Check DB connections, restart connection pool

3. <b>Jika downstream:</b> Check dependency service health

4. <b>Jika overload:</b> Scale up
   <code>kubectl scale deploy &lt;service&gt; -n ecommerce --replicas=3</code>

<b>Escalation:</b> Jika &gt; 5% traffic affected → escalate immediately""",
    },
    "latency": {
        "title": "⏱️ Playbook: High Latency",
        "steps": """<b>Trigger:</b> P95 latency &gt; 2s

<b>Diagnosis Steps:</b>
1. Cek latency per service:
   <code>/latency</code> (bot command)

2. Cek slow traces:
   <code>/traces &lt;service&gt;</code>

3. Cek CPU/Memory (resource saturation):
   <code>/cpu</code> dan <code>/memory</code>

4. Cek traffic spike:
   <code>/traffic</code>

<b>Common Causes:</b>
• N+1 database queries
• Missing index di database
• Resource saturation (CPU/Memory)
• Network issues
• Large payload responses

<b>Remediation:</b>
1. <b>Short-term:</b> Scale up jika resource-bound
2. <b>Medium-term:</b> Add caching (Redis)
3. <b>Long-term:</b> Optimize queries, add DB indexes

<b>Escalation:</b> Jika user-facing P95 &gt; 5s → escalate ke Backend Lead""",
    },
    "disk": {
        "title": "💽 Playbook: Disk Full",
        "steps": """<b>Trigger:</b> Node disk usage &gt; 85%

<b>Diagnosis Steps:</b>
1. SSH ke node / check metrics:
   <code>kubectl get nodes</code>
   <code>kubectl describe node &lt;node-name&gt;</code>

2. Cek apa yang makan disk:
   • Container logs (stdout)
   • Persistent volumes
   • Container images (unused)

<b>Remediation:</b>
1. <b>Immediate:</b> Cleanup unused images
   <code>docker system prune -f</code> (on node)

2. <b>Cleanup old logs:</b>
   Configure log rotation di container runtime

3. <b>Cleanup unused PVCs:</b>
   <code>kubectl get pvc -n ecommerce</code>

4. <b>Long-term:</b> Setup log retention policy di Loki
   Configure disk-based alerts with auto-cleanup

<b>Escalation:</b> Jika &gt; 95% → immediate action required""",
    },
    "notraffic": {
        "title": "📡 Playbook: No Traffic Detected",
        "steps": """<b>Trigger:</b> No frontend/API traffic for 10+ minutes

<b>Diagnosis Steps:</b>
1. Cek apakah ingress/LB accessible:
   <code>kubectl get ingress -n ecommerce</code>
   <code>kubectl get svc -n ecommerce</code>

2. Cek DNS resolution:
   <code>nslookup &lt;domain&gt;</code>

3. Cek frontend pod:
   <code>kubectl get pods -n ecommerce -l app=frontend</code>

4. Cek Faro collector:
   <code>/health</code> (bot command)

<b>Common Causes:</b>
• Ingress controller down
• DNS misconfiguration
• SSL certificate expired
• Frontend deployment failed
• Network policy blocking

<b>Remediation:</b>
1. Cek & restart ingress controller
2. Verify DNS records
3. Check SSL cert expiry
4. Restart frontend pod if needed
5. Check network policies

<b>Escalation:</b> Immediate → ini berarti production down!""",
    },
}


async def playbook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available playbooks."""
    if not is_authorized(update):
        return

    text = "📖 <b>Available Playbooks</b>\n\n"
    text += "/playbook_cpu - High CPU Usage\n"
    text += "/playbook_memory - High Memory / OOMKill\n"
    text += "/playbook_restart - Pod Restart Loop\n"
    text += "/playbook_5xx - High 5xx Error Rate\n"
    text += "/playbook_latency - High Latency\n"
    text += "/playbook_disk - Disk Full\n"
    text += "/playbook_notraffic - No Traffic\n"
    text += "\nKetik command untuk lihat detail playbook."

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def playbook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show specific playbook."""
    if not is_authorized(update):
        return

    # Extract playbook name from command
    command = update.message.text.split("@")[0]  # Remove bot username if present
    pb_name = command.replace("/playbook_", "")

    pb = PLAYBOOKS.get(pb_name)
    if not pb:
        await update.message.reply_text("⚠️ Playbook not found. Gunakan /playbook untuk list.")
        return

    text = f"{pb['title']}\n\n{pb['steps']}"
    await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)


# ==================== INFRA ====================

async def nodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show node CPU and memory from metrics."""
    if not is_authorized(update):
        return

    cpu_data = await _query_mimir('100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)', tenant="nodes")
    mem_data = await _query_mimir('100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))', tenant="nodes")

    text = "🖥️ <b>Node Resources</b>\n\n"

    cpu_results = cpu_data.get("data", {}).get("result", [])
    mem_results = mem_data.get("data", {}).get("result", [])

    if cpu_results:
        text += "<b>CPU Usage:</b>\n"
        for r in cpu_results:
            node = r["metric"].get("node", "unknown")
            val = float(r["value"][1])
            icon = "🔴" if val > 85 else "🟡" if val > 60 else "🟢"
            text += f"{icon} <code>{node[:25]}</code>: {val:.1f}%\n"

    if mem_results:
        text += "\n<b>Memory Usage:</b>\n"
        for r in mem_results:
            node = r["metric"].get("node", "unknown")
            val = float(r["value"][1])
            icon = "🔴" if val > 85 else "🟡" if val > 60 else "🟢"
            text += f"{icon} <code>{node[:25]}</code>: {val:.1f}%\n"

    if not cpu_results and not mem_results:
        text += "⚠️ No node metrics available."

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def pods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pod status in ecommerce namespace."""
    if not is_authorized(update):
        return

    data = await _query_mimir('kube_pod_status_phase{namespace="ecommerce"}')
    results = data.get("data", {}).get("result", [])

    if not results:
        await update.message.reply_text("⚠️ No pod status data available.")
        return

    text = "🫛 <b>Pod Status (ecommerce)</b>\n\n"
    pods_info = {}
    for r in results:
        pod = r["metric"].get("pod", "unknown")
        phase = r["metric"].get("phase", "unknown")
        value = float(r["value"][1])
        if value == 1:
            pods_info[pod] = phase

    for pod, phase in sorted(pods_info.items()):
        icon = "🟢" if phase == "Running" else "🟡" if phase == "Pending" else "🔴"
        text += f"{icon} <code>{pod[:35]}</code>: {phase}\n"

    await update.message.reply_text(text[:4000], parse_mode=ParseMode.HTML)


async def deployments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deployment replica status."""
    if not is_authorized(update):
        return

    desired = await _query_mimir('kube_deployment_spec_replicas{namespace="ecommerce"}')
    available = await _query_mimir('kube_deployment_status_replicas_available{namespace="ecommerce"}')

    desired_results = {r["metric"].get("deployment"): float(r["value"][1]) for r in desired.get("data", {}).get("result", [])}
    available_results = {r["metric"].get("deployment"): float(r["value"][1]) for r in available.get("data", {}).get("result", [])}

    if not desired_results:
        await update.message.reply_text("⚠️ No deployment data available.")
        return

    text = "🚀 <b>Deployments (ecommerce)</b>\n\n"
    for dep in sorted(desired_results.keys()):
        want = int(desired_results.get(dep, 0))
        have = int(available_results.get(dep, 0))
        icon = "🟢" if have >= want else "🔴"
        text += f"{icon} <code>{dep}</code>: {have}/{want} replicas\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ==================== FREE TEXT HANDLER ====================

async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free text messages - forward to AI."""
    if not is_authorized(update):
        return

    question = update.message.text
    if not question:
        return

    await update.message.reply_text("🧠 Thinking...")

    prompt = f"""Kamu adalah SRE/DevOps assistant bot di Telegram untuk monitoring e-commerce app.
Stack: Go microservices, AKS, Grafana LGTM (Loki, Grafana, Tempo, Mimir), Faro RUM.
Services: api-gateway, product-service, order-service, user-service, payment-service, frontend.

User bertanya: {question}

Jawab dalam Bahasa Indonesia. Jika pertanyaan tentang command bot, arahkan ke command yang sesuai.
Jika pertanyaan teknis, jawab singkat dan actionable.
Jika tidak relevan dengan monitoring/infra, bilang sopan bahwa kamu fokus pada monitoring."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            ai_resp = await client.post(
                f"{BEDROCK_PROXY_URL}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": prompt}]},
            )
            ai_data = ai_resp.json()
            answer = ai_data.get("choices", [{}])[0].get("message", {}).get("content", "Maaf, AI tidak tersedia saat ini.")

        await update.message.reply_text(answer[:4000])

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


# ==================== MAIN ====================

async def post_init(application):
    """Set bot commands after startup."""
    commands = [
        BotCommand("start", "Tampilkan menu & bantuan"),
        BotCommand("health", "Health check semua services"),
        BotCommand("alerts", "Alert yang sedang firing"),
        BotCommand("alert_history", "Riwayat alert 24 jam"),
        BotCommand("cpu", "CPU usage per service"),
        BotCommand("memory", "Memory usage per service"),
        BotCommand("latency", "HTTP latency P95"),
        BotCommand("traffic", "Request rate per service"),
        BotCommand("error", "Detail error + log terbaru"),
        BotCommand("errors", "HTTP error rate 4xx/5xx"),
        BotCommand("logs", "Recent logs (semua/per service)"),
        BotCommand("traces", "Slow traces: /traces <service>"),
        BotCommand("incident", "AI incident summary"),
        BotCommand("diagnose", "AI diagnosis: /diagnose <service>"),
        BotCommand("ask", "Tanya AI: /ask <pertanyaan>"),
        BotCommand("playbook", "List semua playbook"),
        BotCommand("nodes", "Node resource usage"),
        BotCommand("pods", "Pod status"),
        BotCommand("deployments", "Deployment status"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is required!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))

    # Status & Health
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("alerts", alerts))
    app.add_handler(CommandHandler("alert_history", alert_history))

    # Metrics
    app.add_handler(CommandHandler("cpu", cpu))
    app.add_handler(CommandHandler("memory", memory))
    app.add_handler(CommandHandler("latency", latency))
    app.add_handler(CommandHandler("traffic", traffic))
    app.add_handler(CommandHandler("error", error_detail))
    app.add_handler(CommandHandler("errors", errors))

    # Logs
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("logs_error", logs_error))
    app.add_handler(CommandHandler("logs_all", logs_all))

    # Traces
    app.add_handler(CommandHandler("traces", traces))
    app.add_handler(CommandHandler("trace", trace_detail))

    # AI
    app.add_handler(CommandHandler("incident", incident))
    app.add_handler(CommandHandler("diagnose", diagnose))
    app.add_handler(CommandHandler("ask", ask))

    # Playbooks
    app.add_handler(CommandHandler("playbook", playbook))
    app.add_handler(CommandHandler("playbook_cpu", playbook_handler))
    app.add_handler(CommandHandler("playbook_memory", playbook_handler))
    app.add_handler(CommandHandler("playbook_restart", playbook_handler))
    app.add_handler(CommandHandler("playbook_5xx", playbook_handler))
    app.add_handler(CommandHandler("playbook_latency", playbook_handler))
    app.add_handler(CommandHandler("playbook_disk", playbook_handler))
    app.add_handler(CommandHandler("playbook_notraffic", playbook_handler))

    # Infra
    app.add_handler(CommandHandler("nodes", nodes))
    app.add_handler(CommandHandler("pods", pods))
    app.add_handler(CommandHandler("deployments", deployments))

    # Free text → AI
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, free_text))

    logger.info("🤖 LGTM Ops Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
