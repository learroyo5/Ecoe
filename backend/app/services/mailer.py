"""Transactional email for team invitations and access resets.

Best-effort: si SMTP no esta configurado (entornos locales/demo) o el envio
falla, se registra un log y se devuelve False. El enlace de activacion sigue
disponible en la respuesta de la API para repartir a mano, como respaldo.
"""

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import ECOEEvent
from app.models.enums import RoleCode

logger = logging.getLogger("ecoe.mailer")

ROLE_LABELS: dict[str, str] = {
    RoleCode.admin_ecoe.value: "administrador del ECOE",
    RoleCode.coeditor_docente.value: "coeditor docente",
    RoleCode.evaluador.value: "evaluador",
    RoleCode.coordinador_operativo.value: "coordinador operativo",
    RoleCode.cronometrador.value: "cronometrador",
}


def send_email(*, to: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        logger.info("smtp_not_configured to=%s subject=%r", to, subject)
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_user
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        logger.info("email_sent to=%s subject=%r", to, subject)
        return True
    except Exception:
        logger.exception("email_send_failed to=%s subject=%r", to, subject)
        return False


def send_event_access_email(
    *, to: str, ecoe_event_name: str, role_label: str, activation_path: str, is_reset: bool
) -> bool:
    settings = get_settings()
    link = f"{settings.public_app_url.rstrip('/')}{activation_path}"
    if is_reset:
        subject = f"Tu acceso a {ecoe_event_name} fue reiniciado"
        intro = (
            f"Tu acceso como {role_label} en el ECOE \"{ecoe_event_name}\" fue reiniciado "
            "por un administrador o coeditor de ese evento."
        )
    else:
        subject = f"Invitación al ECOE {ecoe_event_name}"
        intro = (
            f"Fuiste incorporado como {role_label} al ECOE \"{ecoe_event_name}\" en la "
            "plataforma de gestión de ECOE/OSCE."
        )
    body = (
        f"{intro}\n\n"
        f"Define tu contraseña personal para ingresar (nadie más la ve) en:\n{link}\n\n"
        "El enlace es de un solo uso y expira pronto; si ya venció, pide a quien te "
        "invitó que genere uno nuevo desde la pantalla Evaluadores del ECOE.\n"
    )
    return send_email(to=to, subject=subject, body=body)


def notify_event_access(db: Session, ecoe_event_id: int, result: dict, *, is_reset: bool) -> bool:
    """Send the access email for an assign_or_invite_member/reset_active_member_access result.

    No-op (returns False) when the result did not actually issue a link, e.g.
    an existing account that was just assigned (status "assigned").
    """
    activation_path = result.get("activation_path")
    if not activation_path:
        return False
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    return send_event_access_email(
        to=result["email"],
        ecoe_event_name=ecoe_event.name if ecoe_event else "ECOE",
        role_label=ROLE_LABELS.get(result.get("role_code", ""), "colaborador"),
        activation_path=activation_path,
        is_reset=is_reset,
    )
