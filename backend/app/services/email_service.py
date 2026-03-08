"""이메일 인증 서비스

Gmail SMTP를 사용한 이메일 인증 코드 발송
"""
import random
import smtplib
import logging
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("email_service")


def _generate_code() -> str:
    """6자리 숫자 인증 코드 생성"""
    return str(random.randint(100000, 999999))


def _send_mail_sync(to_email: str, code: str) -> None:
    """Gmail SMTP로 인증 메일 발송 (동기, 스레드풀용)"""
    msg = EmailMessage()
    msg["Subject"] = f"[SignTalk] Verification Code: {code}"
    msg["From"] = f"SignTalk <{settings.SMTP_USER}>"
    msg["To"] = to_email

    # 텍스트 본문 (ASCII only — SMTP 호환)
    msg.set_content(f"SignTalk verification code: {code}\nValid for 5 minutes.")

    # HTML 본문 (한글 가능 — UTF-8 인코딩으로 별도 파트 전송)
    html_body = f"""<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px">
<h2 style="color:#4A90D9">SignTalk 이메일 인증</h2>
<p>아래 인증 코드를 회원가입 화면에 입력해주세요.</p>
<div style="font-size:36px;font-weight:bold;text-align:center;
padding:24px;background:#f0f4ff;border-radius:8px;color:#1a3a6e;margin:24px 0">{code}</div>
<p style="color:#888;font-size:13px">이 코드는 5분간 유효합니다.<br>본인이 요청하지 않았다면 무시하세요.</p>
</div>"""
    msg.add_alternative(html_body, subtype="html", charset="utf-8")

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)

    logger.info(f"인증 메일 발송 완료 -> {to_email}")


async def send_verification_email(to_email: str) -> str:
    """인증 코드를 생성하고 메일로 발송 후 코드 반환 (비동기 래퍼)"""
    from fastapi.concurrency import run_in_threadpool
    code = _generate_code()
    await run_in_threadpool(_send_mail_sync, to_email, code)
    return code
