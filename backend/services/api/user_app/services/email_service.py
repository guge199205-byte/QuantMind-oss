"""
Email Verification and Password Reset Service
邮箱验证和密码重置服务
"""

import asyncio
import logging
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.api.user_app.config import settings
from backend.services.api.user_app.models.rbac import (
    EmailVerification,
    PasswordResetToken,
)
from backend.services.api.user_app.models.user import User

logger = logging.getLogger(__name__)


class EmailService:
    """
    企业级邮件服务驱动
    支持 SMTP 真实发送与 Logger 降级模式。
    """

    def __init__(self, db: AsyncSession = None):
        self.db = db
        # 核心配置项
        self.smtp_host = os.getenv("SMTP_HOST") or getattr(settings, "SMTP_HOST", None)
        self.smtp_port = int(
            os.getenv("SMTP_PORT") or getattr(settings, "SMTP_PORT", 465)
        )
        self.smtp_user = os.getenv("SMTP_USER") or getattr(settings, "SMTP_USER", None)
        self.smtp_pass = os.getenv("SMTP_PASSWORD") or getattr(
            settings, "SMTP_PASSWORD", None
        )
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.sender_email = os.getenv("SENDER_EMAIL") or getattr(
            settings, "SENDER_EMAIL", self.smtp_user
        )
        self.sender_name = os.getenv("SENDER_NAME", "QuantMind Support")

    async def _send_mail(
        self, subject: str, recipient: str, html_content: str, text_content: str = ""
    ) -> bool:
        """
        统一发送逻辑。
        若未配置 SMTP，则自动降级为日志输出。
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("[Mail] ⚠️ 未配置 SMTP，邮件将降级为日志输出模式。")
            self._log_mail_mock(subject, recipient, text_content or html_content)
            return True

        try:
            # 使用 asyncio.to_thread 运行同步的 smtplib 避免阻塞事件循环
            return await asyncio.to_thread(
                self._send_mail_sync, subject, recipient, html_content, text_content
            )
        except Exception as e:
            logger.error(f"[Mail] ❌ 邮件发送失败 ({recipient}): {e}")
            return False

    def _send_mail_sync(
        self, subject: str, recipient: str, html_content: str, text_content: str = ""
    ) -> bool:
        """同步发送逻辑"""
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{self.sender_name} <{self.sender_email}>"
        message["To"] = recipient

        # 注入纯文本与 HTML 两部分，确保兼容性
        part1 = MIMEText(
            text_content or "Please use an HTML compatible email client.", "plain"
        )
        part2 = MIMEText(html_content, "html")
        message.attach(part1)
        message.attach(part2)

        # 根据端口决定是否使用 SSL
        if self.smtp_port == 465:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as server:
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.sender_email, recipient, message.as_string())
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.sender_email, recipient, message.as_string())

        logger.info(f"[Mail] ✅ 邮件已成功发送至 {recipient}")
        return True

    def _log_mail_mock(self, subject: str, recipient: str, content: str):
        """Mock 模式下的详细日志输出"""
        divider = "=" * 60
        logger.info(
            f"\n{divider}\n[MOCK EMAIL SENT]\nTo: {recipient}\nSubject: {subject}\nContent: {content[:500]}...\n{divider}"
        )

    async def send_verification_email(
        self, email: str, verification_code: str, code_type: str
    ) -> bool:
        """发送验证邮件 (HTML)"""
        title_map = {
            "register": "欢迎加入 QuantMind - 请验证您的邮箱",
            "reset_password": "重置您的 QuantMind 账户密码",
            "change_email": "确认修改您的 QuantMind 邮箱",
        }
        subject = title_map.get(code_type, "QuantMind 安全验证码")

        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
            <h2 style="color: #2563eb;">QuantMind 验证码</h2>
            <p>您好，您正在进行 <b>{subject}</b> 操作。</p>
            <div style="background: #f3f4f6; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #1f2937; margin: 20px 0;">
                {verification_code}
            </div>
            <p style="color: #6b7280; font-size: 14px;">此验证码 30 分钟内有效。如果不是您本人操作，请忽略此邮件。</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #9ca3af;">QuantMind Quant-Trading Platform | 企业级量化交易平台</p>
        </div>
        """
        return await self._send_mail(
            subject, email, html, f"您的验证码是: {verification_code}"
        )

    async def send_password_reset_email(self, email: str, reset_token: str) -> bool:
        """发送密码重置链接"""
        subject = "重置您的 QuantMind 密码"
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        reset_link = f"{frontend_url}/auth/reset-password?token={reset_token}"

        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #eee; padding: 20px;">
            <h2 style="color: #ef4444;">重置密码请求</h2>
            <p>我们收到了重置您 QuantMind 账户密码的请求。</p>
            <p>请点击下方按钮设置新密码：</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" style="background: #2563eb; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">重置密码</a>
            </div>
            <p style="color: #6b7280; font-size: 14px;">或者复制此链接至浏览器：<br>{reset_link}</p>
            <p style="color: #6b7280; font-size: 14px;">此链接 24 小时内有效。如果不是您申请的，请忽略。</p>
        </div>
        """
        return await self._send_mail(
            subject, email, html, f"请访问此链接重置密码: {reset_link}"
        )

    async def send_welcome_email(self, email: str, username: str) -> bool:
        """发送欢迎邮件"""
        subject = f"欢迎来到 QuantMind, {username}!"
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">欢迎加入 QuantMind!</h2>
            <p>尊敬的 {username}，您的账户已准备就绪。</p>
            <p>QuantMind 为您提供了一站式的 AI 驱动量化交易体验，您可以开始探索我们的策略工作台了。</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{frontend_url}/dashboard" style="background: #10b981; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">进入控制台</a>
            </div>
        </div>
        """
        return await self._send_mail(
            subject, email, html, f"欢迎加入 QuantMind, {username}!"
        )


class VerificationService:
    """邮箱验证服务 (保持逻辑不变，适配新的 EmailService)"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService(db)

    def generate_verification_code(self, length: int = 32) -> str:
        """生成验证码"""
        return secrets.token_urlsafe(length)

    async def create_verification_code(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        code_type: str,
        ip_address: str | None = None,
        expires_in_minutes: int = 30,
    ) -> str:
        """创建验证码"""
        # 生成验证码 (这里可以使用纯数字以便于手机/邮件输入)
        verification_code = "".join([str(secrets.randbelow(10)) for _ in range(6)])

        # 创建记录
        verification = EmailVerification(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            verification_code=verification_code,
            code_type=code_type,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=expires_in_minutes),
            is_used=False,
            is_expired=False,
            attempts=0,
        )

        self.db.add(verification)
        await self.db.commit()

        # 发送验证邮件
        await self.email_service.send_verification_email(
            email, verification_code, code_type
        )

        logger.info(f"✅ 创建验证码成功: {user_id} - {code_type}")

        return verification_code

    async def verify_code(
        self,
        verification_code: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        code_type: str | None = None,
    ) -> tuple[bool, str | None]:
        """验证码验证"""
        stmt = select(EmailVerification).where(
            EmailVerification.verification_code == verification_code
        )

        if user_id:
            stmt = stmt.where(EmailVerification.user_id == user_id)
        if tenant_id:
            stmt = stmt.where(EmailVerification.tenant_id == tenant_id)
        if code_type:
            stmt = stmt.where(EmailVerification.code_type == code_type)

        result = await self.db.execute(stmt)
        verification = result.scalar_one_or_none()

        if not verification:
            return False, "验证码不存在"
        if verification.is_used:
            return False, "验证码已使用"

        now = datetime.now(timezone.utc)
        if verification.is_expired or verification.expires_at < now:
            verification.is_expired = True
            await self.db.commit()
            return False, "验证码已过期"

        if verification.attempts >= 5:
            return False, "验证次数过多，请重新获取"

        verification.attempts += 1
        verification.is_used = True
        verification.used_at = now
        await self.db.commit()

        logger.info(f"✅ 验证码验证成功: {verification.user_id}")
        return True, verification.user_id

    async def invalidate_user_codes(self, user_id: str, tenant_id: str, code_type: str):
        """使用户的所有相同类型验证码失效"""
        stmt = select(EmailVerification).where(
            and_(
                EmailVerification.user_id == user_id,
                EmailVerification.tenant_id == tenant_id,
                EmailVerification.code_type == code_type,
                EmailVerification.is_used == False,
            )
        )
        result = await self.db.execute(stmt)
        verifications = result.scalars().all()

        for verification in verifications:
            verification.is_expired = True

        await self.db.commit()


class PasswordResetService:
    """密码重置服务 (适配新的 EmailService)"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService(db)

    async def create_reset_token(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        ip_address: str | None = None,
        expires_in_hours: int = 24,
    ) -> str:
        """创建密码重置令牌"""
        reset_token = secrets.token_urlsafe(32)

        token_record = PasswordResetToken(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            token=reset_token,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
            is_used=False,
            is_expired=False,
            attempts=0,
        )

        self.db.add(token_record)
        await self.db.commit()

        # 发送重置邮件
        await self.email_service.send_password_reset_email(email, reset_token)

        logger.info(f"✅ 创建密码重置令牌: {user_id}")
        return reset_token

    async def verify_reset_token(
        self, reset_token: str, tenant_id: str
    ) -> tuple[bool, str | None]:
        """验证重置令牌"""
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token == reset_token,
            PasswordResetToken.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            return False, "重置令牌不存在"
        if token_record.is_used:
            return False, "重置令牌已使用"
        if token_record.is_expired or token_record.expires_at < datetime.now(
            timezone.utc
        ):
            token_record.is_expired = True
            await self.db.commit()
            return False, "重置令牌已过期"

        token_record.attempts += 1
        await self.db.commit()
        return True, token_record.user_id

    async def reset_password(
        self, reset_token: str, tenant_id: str, new_password: str
    ) -> tuple[bool, str | None]:
        """重置密码逻辑与 User 模型同步"""
        success, result = await self.verify_reset_token(reset_token, tenant_id)
        if not success:
            return False, result

        user_id = result
        stmt = select(User).where(
            User.user_id == user_id,
            User.tenant_id == tenant_id,
        )
        db_result = await self.db.execute(stmt)
        user = db_result.scalar_one_or_none()

        if not user:
            return False, "用户不存在"

        # 使用 AuthService 的哈希逻辑 (此处导入避免循环依赖)
        from backend.services.api.user_app.services.auth_service import AuthService

        auth_service = AuthService()
        user.password_hash = auth_service._hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)

        token_record_stmt = select(PasswordResetToken).where(
            PasswordResetToken.token == reset_token
        )
        tr_res = await self.db.execute(token_record_stmt)
        token_record = tr_res.scalar_one_or_none()
        if token_record:
            token_record.is_used = True
            token_record.used_at = datetime.now(timezone.utc)

        await self.db.commit()
        logger.info(f"✅ 密码重置成功: {user_id}")
        return True, None
