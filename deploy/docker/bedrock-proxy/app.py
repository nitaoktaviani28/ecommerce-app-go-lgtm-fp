import os
import json
import smtplib
import logging
import threading
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
import boto3

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS Bedrock config
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "amazon.nova-lite-v1:0")

# SMTP config
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "nitaoktaviani2005@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "eizdtilrlqcnyzui")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "nitaoktaviani2005@gmail.com")

# Bedrock client
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def call_bedrock(prompt):
    """Call AWS Bedrock with Converse API."""
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 1024, "temperature": 0.3},
    )
    return response["output"]["message"]["content"][0]["text"]


def send_email(subject, body_html):
    """Send email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL_TO
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())
    logger.info(f"Email sent to {ALERT_EMAIL_TO}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "model": MODEL_ID})


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """OpenAI-compatible chat completions endpoint."""
    data = request.get_json()
    messages = data.get("messages", [])

    # Extract last user message
    prompt = ""
    for msg in messages:
        if msg.get("role") == "user":
            prompt = msg.get("content", "")

    if not prompt:
        return jsonify({"error": "No user message found"}), 400

    try:
        result = call_bedrock(prompt)
        return jsonify(
            {
                "id": "chatcmpl-bedrock",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result},
                        "finish_reason": "stop",
                    }
                ],
                "model": MODEL_ID,
            }
        )
    except Exception as e:
        logger.error(f"Bedrock error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v1/models", methods=["GET"])
def list_models():
    """OpenAI-compatible models listing."""
    return jsonify(
        {
            "data": [
                {"id": MODEL_ID, "object": "model", "owned_by": "aws-bedrock"},
                {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "aws-bedrock"},
                {"id": "gpt-4", "object": "model", "owned_by": "aws-bedrock"},
            ]
        }
    )


@app.route("/webhook/alert", methods=["POST"])
def webhook_alert():
    """Receive Grafana alert webhook → only process resolved alerts for AI summary."""
    data = request.get_json()
    logger.info(f"Received alert webhook: {json.dumps(data, indent=2)[:500]}")

    # Extract alert info
    title = data.get("title", "Grafana Alert")
    status = data.get("status", "unknown")
    alerts = data.get("alerts", [])

    alert_details = []
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alert_details.append(
            f"- Alert: {labels.get('alertname', 'N/A')}\n"
            f"  Severity: {labels.get('severity', 'N/A')}\n"
            f"  Summary: {annotations.get('summary', 'N/A')}\n"
            f"  Description: {annotations.get('description', 'N/A')}\n"
            f"  Status: {alert.get('status', 'N/A')}"
        )

    alert_text = "\n".join(alert_details) if alert_details else "No alert details"

    if status == "resolved":
        # Generate and send AI Incident Summary (in background thread)
        # Resolved email is already sent by Grafana email contact point
        thread = threading.Thread(
            target=_send_ai_incident_summary,
            args=[title, alert_text, alerts],
            daemon=True,
        )
        thread.start()

        return jsonify({"status": "ok", "message": "AI incident summary generating..."})
    else:
        # Firing: do nothing here, Grafana email contact point handles firing notification
        logger.info(f"Alert firing received for '{title}' — email handled by Grafana contact point")
        return jsonify({"status": "ok", "message": "Firing alert acknowledged, email sent by Grafana"})


def _format_to_wib(iso_str):
    """Convert ISO timestamp to WIB (UTC+7) readable format."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        wib = dt.astimezone(timezone(timedelta(hours=7)))
        return wib.strftime("%d %B %Y %H:%M WIB")
    except Exception:
        return iso_str


def _send_ai_incident_summary(title, alert_text, alerts):
    """Generate AI Incident Summary after resolved email is sent."""
    # Calculate duration from alert timestamps
    durations = []
    for alert in alerts:
        starts_at = alert.get("startsAt", "")
        ends_at = alert.get("endsAt", "")
        if starts_at and ends_at:
            durations.append(f"  Start: {_format_to_wib(starts_at)}, End: {_format_to_wib(ends_at)}")

    duration_text = "\n".join(durations) if durations else "Duration unknown"

    prompt = f"""You are an SRE assistant. An alert has fired and is now resolved.
Write a brief Incident Summary (NOT a full post-mortem).

Include:
1. **What happened** - One paragraph summary of the incident
2. **Duration** - How long the incident lasted
3. **Impact** - What was affected
4. **Resolution** - What likely resolved it
5. **Recommendation** - One or two key actions to prevent recurrence

Alert Information:
- Title: {title}
- Status: RESOLVED
- Duration:
{duration_text}
- Details:
{alert_text}

Environment: Docker Swarm on Azure VM (Grafana LGTM stack)
Services: ecommerce app (api-gateway, product, order, user, payment services)

Keep it concise and actionable. Format as HTML suitable for email."""

    try:
        ai_summary = call_bedrock(prompt)
        logger.info("AI Incident Summary generated successfully")

        email_subject = f"[AI Incident Summary] {title}"
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">🤖 AI Incident Summary</h2>
            <p><strong>Alert:</strong> {title}</p>
            <p><strong>Status:</strong> ✅ RESOLVED</p>
            <p><strong>Generated at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC+7')}</p>
            <hr>
            <div>{ai_summary}</div>
            <hr>
            <p style="color: #666; font-size: 12px;">
                Generated by AWS Bedrock ({MODEL_ID}) | Grafana LGTM Stack<br>
                This summary was generated automatically after alert resolution.
            </p>
        </body>
        </html>
        """
        send_email(email_subject, email_body)
        logger.info("AI Incident Summary email sent")
    except Exception as e:
        logger.error(f"AI Incident Summary error: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4000)
