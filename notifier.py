"""
Multi-channel alert notification system
"""
import asyncio
import aiohttp
import smtplib
import base64
from typing import Optional
from datetime import datetime
from loguru import logger
from config.settings import settings
from events.event_engine import SecurityEvent


class AlertNotifier:
    """
    Sends alerts via Telegram, Email, Webhook, and push notifications.
    """
    
    async def send_all(self, event: SecurityEvent):
        """Send alert through all configured channels"""
        tasks = []
        
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            tasks.append(self._send_telegram(event))
        
        if settings.SENDGRID_API_KEY:
            tasks.append(self._send_email(event))
        
        if settings.WEBHOOK_URL:
            tasks.append(self._send_webhook(event))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Alert channel {i} failed: {result}")
    
    async def _send_telegram(self, event: SecurityEvent):
        """Send Telegram message with optional photo"""
        emoji_map = {
            "unknown_person": "🚨",
            "loitering": "⚠️",
            "intrusion": "🔴",
            "night_activity": "🌙",
            "package_delivered": "📦",
            "package_removed": "📦",
            "door_interaction": "🚪",
            "known_person": "✅",
        }
        
        emoji = emoji_map.get(event.event_type, "🔔")
        severity_upper = event.severity.upper()
        
        message = (
            f"{emoji} *Security Alert* [{severity_upper}]\n\n"
            f"*Event:* {event.description}\n"
            f"*Camera:* {event.camera_name}\n"
            f"*Time:* {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        if event.person_name:
            message += f"*Person:* {event.person_name}\n"
        if event.zone_name:
            message += f"*Zone:* {event.zone_name}\n"
        
        base_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
        
        async with aiohttp.ClientSession() as session:
            try:
                if event.snapshot:
                    # Send photo with caption
                    form = aiohttp.FormData()
                    form.add_field("chat_id", settings.TELEGRAM_CHAT_ID)
                    form.add_field("caption", message)
                    form.add_field("parse_mode", "Markdown")
                    form.add_field("photo", event.snapshot,
                                  content_type="image/jpeg",
                                  filename="snapshot.jpg")
                    
                    async with session.post(f"{base_url}/sendPhoto", data=form) as resp:
                        if resp.status == 200:
                            logger.success(f"Telegram photo alert sent: {event.event_type}")
                        else:
                            body = await resp.text()
                            logger.error(f"Telegram error {resp.status}: {body}")
                else:
                    # Text only
                    payload = {
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": message,
                        "parse_mode": "Markdown",
                    }
                    async with session.post(f"{base_url}/sendMessage", json=payload) as resp:
                        if resp.status == 200:
                            logger.success(f"Telegram text alert sent: {event.event_type}")
                        else:
                            body = await resp.text()
                            logger.error(f"Telegram error {resp.status}: {body}")
            
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
    
    async def _send_email(self, event: SecurityEvent):
        """Send email alert via SendGrid"""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType
            
            sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            
            html_content = f"""
            <html><body>
            <h2>🔔 Security Alert - {event.severity.upper()}</h2>
            <table>
                <tr><td><b>Event:</b></td><td>{event.description}</td></tr>
                <tr><td><b>Camera:</b></td><td>{event.camera_name}</td></tr>
                <tr><td><b>Time:</b></td><td>{event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
                <tr><td><b>Type:</b></td><td>{event.event_type}</td></tr>
                {f'<tr><td><b>Person:</b></td><td>{event.person_name}</td></tr>' if event.person_name else ''}
                {f'<tr><td><b>Zone:</b></td><td>{event.zone_name}</td></tr>' if event.zone_name else ''}
            </table>
            </body></html>
            """
            
            mail = Mail(
                from_email=settings.ALERT_EMAIL_FROM,
                to_emails=settings.ALERT_EMAIL_TO,
                subject=f"Security Alert: {event.event_type} - {event.camera_name}",
                html_content=html_content,
            )
            
            if event.snapshot:
                encoded = base64.b64encode(event.snapshot).decode()
                attachment = Attachment(
                    FileContent(encoded),
                    FileName("snapshot.jpg"),
                    FileType("image/jpeg"),
                )
                mail.attachment = attachment
            
            sg.send(mail)
            logger.success(f"Email alert sent for {event.event_type}")
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
    
    async def _send_webhook(self, event: SecurityEvent):
        """Send webhook POST with event data"""
        payload = {
            "event_type": event.event_type,
            "severity": event.severity,
            "camera_id": event.camera_id,
            "camera_name": event.camera_name,
            "description": event.description,
            "timestamp": event.timestamp.isoformat(),
            "person_name": event.person_name,
            "zone_name": event.zone_name,
            "track_id": event.track_id,
            "has_snapshot": event.snapshot is not None,
        }
        
        headers = {"Content-Type": "application/json"}
        if settings.WEBHOOK_SECRET:
            headers["X-Security-Secret"] = settings.WEBHOOK_SECRET
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.WEBHOOK_URL, json=payload, headers=headers, timeout=10
                ) as resp:
                    if resp.status < 300:
                        logger.success(f"Webhook sent: {event.event_type}")
                    else:
                        logger.error(f"Webhook failed {resp.status}")
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")


# Global notifier
notifier = AlertNotifier()
