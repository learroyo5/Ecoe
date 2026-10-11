"""Estaciones sugeridas desde una guía de simulación (services/guide_import.py).

El modelo nunca se llama de verdad: `request_station_suggestions` se reemplaza
por una respuesta fija. Se prueba lo que es responsabilidad del servidor:
lectura del archivo, datos personales, forma de la respuesta y permisos.
"""

import io
import zipfile

import pytest

from conftest import ADMIN, COEDITOR, COORDINATOR, EVALUATOR, STUDENT, TestingSessionLocal, login
from app.core.config import get_settings
from app.models.entities import AssessmentTool, AuditLog, Station
from app.services import guide_import
from sqlalchemy import func, select

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _table(rows: list[list[str]]) -> str:
    body = "".join(
        "<w:tr>" + "".join(f"<w:tc>{_paragraph(cell)}</w:tc>" for cell in row) + "</w:tr>"
        for row in rows
    )
    return f"<w:tbl>{body}</w:tbl>"


def make_docx(body_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W_NS}"><w:body>{body_xml}</w:body></w:document>',
        )
    return buffer.getvalue()


GUIDE_BODY = (
    _paragraph("Instructivo de diseño de escenario de simulación Sim Zone 1")
    + _table([["Nombre de la actividad"], ["Higienización de manos"]])
    + _table([
        ["Nombre y Apellidos del o la docente (responsable)", "Juana Pérez Soto"],
        ["Fono de contacto", "+569 5555 1234"],
        ["RUT", "12.345.678-9"],
        ["Correo", "juana.perez@uct.cl"],
    ])
    + _paragraph(
        "Los estudiantes se ubican en duplas frente a un lavamanos; dudas a docente@uct.cl "
        "o al 15655142-2. " + "Realiza lavado clínico de manos. " * 12
    )
    + _table([
        ["Criterios de Evaluación", "Ptje. Ítem"],
        ["Retira joyas, reloj y se descubre los brazos hasta el codo.", "1"],
        ["Se frota las palmas de las manos entre sí.", "1"],
    ])
    + _paragraph("ANEXO: GLOSARIO")
    + _paragraph("Brief: actividad anterior al inicio de una simulación.")
)

RAW_SUGGESTION = {
    "guide_title": "Higienización de manos",
    "summary": "Dos técnicas, dos estaciones.",
    "warnings": ["La pauta de alcohol gel declara 12 puntos."],
    "stations": [
        {
            "name": "Higiene de manos con alcohol gel",
            "station_type": "procedimental",
            "rationale": "La guía trae una pauta propia para esta técnica.",
            "suggested_minutes": 3,
            "expected_outcomes": "Realiza higienización con alcohol gel.",
            "student_activity": "Realiza la técnica completa.",
            "pre_entry_instruction": "Higieniza tus manos con alcohol gel.",
            "student_station_instruction": "",
            "evaluator_instruction": "Observa sin guiar.",
            "materials": "Frasco de alcohol gel: 1",
            "requires_evaluator": True,
            "requires_student_form": False,
            "instrument": {
                "name": "Pauta alcohol gel",
                "tool_type": "lista_cotejo",
                "declared_total": 12,
                "items": [{"label": f"Criterio {n}", "score": 1} for n in range(1, 11)],
            },
            "field_sources": {"expected_outcomes": "guia", "materials": "guia", "ambience": "guia"},
        },
        {
            "name": "Buzón: fundamentos",
            "station_type": "conceptual",
            "rationale": "Preguntas de activación de la guía.",
            "expected_outcomes": "Reconoce la importancia del lavado de manos.",
            "student_activity": "Responde por escrito.",
            "requires_evaluator": False,
            "requires_student_form": True,
            "instrument": {"name": "x", "tool_type": "lista_cotejo", "items": [{"label": "a", "score": 1}]},
            "student_questions": [
                {
                    "label": "¿Cuánto dura el lavado clínico?",
                    "type": "single_choice",
                    "options": ["20 a 30 s", "40 a 60 s"],
                    "correct_options": ["40 a 60 s"],
                    "points": 2,
                },
                {
                    "label": "¿Qué previene?",
                    "type": "single_choice",
                    "options": ["IAAS", "Caries"],
                    "correct_options": ["Otra cosa"],
                    "points": 1,
                },
                {"label": "Explica por qué.", "type": "short_text", "points": 3},
            ],
        },
    ],
}


@pytest.fixture
def ai_enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    sent: list[str] = []

    def fake_request(guide_text: str):
        sent.append(guide_text)
        return RAW_SUGGESTION

    monkeypatch.setattr(guide_import, "request_station_suggestions", fake_request)
    guide_import._JOBS.clear()
    yield sent
    guide_import._JOBS.clear()


def _upload(client, data: bytes = None, filename: str = "guia.docx"):
    return client.post(
        "/api/station-guide/suggest?ecoe_event_id=1",
        files={"file": (filename, data if data is not None else make_docx(GUIDE_BODY), "application/octet-stream")},
    )


class TestExtraction:
    def test_docx_keeps_tables_and_drops_personal_data_and_glossary(self):
        text, truncated = guide_import.prepare_guide_text("guia.docx", make_docx(GUIDE_BODY))
        assert not truncated
        assert "| Retira joyas, reloj y se descubre los brazos hasta el codo. | 1 |" in text
        assert "Higienización de manos" in text
        for leaked in ("Juana", "5555", "12.345.678-9", "juana.perez@uct.cl", "docente@uct.cl", "15655142-2"):
            assert leaked not in text
        assert "GLOSARIO" not in text

    def test_pdf_text_is_extracted(self):
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        for line in range(12):
            pdf.drawString(72, 780 - line * 18, f"Paso {line}: administra el medicamento por via intramuscular.")
        pdf.save()
        text = guide_import.extract_guide_text("guia.pdf", buffer.getvalue())
        assert "via intramuscular" in text

    @pytest.mark.parametrize(
        "filename,data",
        [
            ("guia.docx", b"esto no es un zip"),
            ("guia.docx", b"PK\x03\x04 zip roto"),
            ("guia.pdf", b"%PDF-1.7 basura sin estructura"),
            ("guia.exe", b"MZ\x90\x00"),
            ("guia.docx", b"%PDF-1.4 extension que no calza con el contenido"),
            ("guia.docx", make_docx(_paragraph("muy corta"))),
        ],
    )
    def test_invalid_files_are_rejected(self, filename, data):
        with pytest.raises(guide_import.GuideImportError):
            guide_import.extract_guide_text(filename, data)

    def test_docx_without_document_xml_rejected(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("otra/cosa.txt", "x" * 500)
        with pytest.raises(guide_import.GuideImportError):
            guide_import.extract_guide_text("guia.docx", buffer.getvalue())


class TestNormalization:
    def test_scores_are_recomputed_and_mismatch_is_flagged(self):
        result = guide_import.normalize_suggestions(RAW_SUGGESTION)
        gel = result["stations"][0]
        assert gel["instrument"]["max_score"] == 10
        assert gel["max_score"] == 10
        assert any("declara 12" in warning for warning in gel["warnings"])
        assert gel["field_sources"]["expected_outcomes"] == "guia"
        # Completado sin declarar origen: se trata como redacción de la IA.
        assert gel["field_sources"]["evaluator_instruction"] == "ia"
        # Declarado "guia" pero vacío: no se le cree.
        assert gel["field_sources"]["ambience"] == "falta"
        assert "instrucciones dentro de la estación" in gel["missing"]

    def test_form_station_drops_instrument_and_checks_answer_key(self):
        box = guide_import.normalize_suggestions(RAW_SUGGESTION)["stations"][1]
        assert box["requires_evaluator"] is False
        assert box["instrument"] is None
        questions = box["student_form_definition"]["questions"]
        assert questions[0]["correct_option"] == "40 a 60 s"
        # Clave que no es una de las opciones: se descarta y se avisa.
        assert questions[1]["correct_option"] is None
        assert any("pregunta 2" in warning for warning in box["warnings"])
        assert box["requires_deferred_grading"] is True
        assert box["max_score"] == 6

    def test_garbage_from_model_never_breaks(self):
        result = guide_import.normalize_suggestions({
            "stations": [
                None,
                "texto",
                {"name": ""},
                {
                    "name": "X" * 900,
                    "station_type": "inventado",
                    "requires_evaluator": True,
                    "requires_student_form": True,
                    "instrument": {"items": [{"label": "ok", "score": -5}, {"label": "", "score": 1}, 7]},
                    "student_questions": "no es lista",
                    "suggested_minutes": 9999,
                    "field_sources": ["x"],
                },
            ],
        })
        assert len(result["stations"]) == 1
        station = result["stations"][0]
        assert len(station["name"]) == 255
        assert station["station_type"] == "procedimental"
        assert station["instrument"]["items"] == [{"label": "ok", "score_per_item": 1.0}]
        assert station["requires_student_form"] is False
        assert station["suggested_minutes"] is None

    def test_non_dict_response_is_an_error(self):
        with pytest.raises(guide_import.GuideImportError):
            guide_import.normalize_suggestions(["x"])

    def test_no_stations_explains_itself(self):
        result = guide_import.normalize_suggestions({"stations": []})
        assert result["stations"] == []
        assert result["warnings"]


class TestEndpoints:
    def test_full_flow_returns_suggestions_without_writing_stations(self, auth_client, ai_enabled):
        with TestingSessionLocal() as db:
            before = (db.scalar(select(func.count(Station.id))), db.scalar(select(func.count(AssessmentTool.id))))
        response = _upload(auth_client)
        assert response.status_code == 202, response.text
        job = auth_client.get(f"/api/station-guide/jobs/{response.json()['job_id']}").json()
        assert job["status"] == "done"
        assert [station["name"] for station in job["result"]["stations"]] == [
            "Higiene de manos con alcohol gel",
            "Buzón: fundamentos",
        ]
        # Lo que salió hacia el modelo no lleva datos del docente.
        assert "juana.perez@uct.cl" not in ai_enabled[0] and "Juana" not in ai_enabled[0]
        with TestingSessionLocal() as db:
            after = (db.scalar(select(func.count(Station.id))), db.scalar(select(func.count(AssessmentTool.id))))
            audit = db.scalars(
                select(AuditLog).where(AuditLog.action == "suggest_stations_from_guide")
            ).all()
        assert after == before
        assert audit and audit[-1].payload["filename"] == "guia.docx"
        assert "Juana" not in str(audit[-1].payload)

    def test_coeditor_allowed(self, client, ai_enabled):
        login(client, COEDITOR)
        assert client.get("/api/station-guide/status").json()["enabled"] is True
        assert _upload(client).status_code == 202

    @pytest.mark.parametrize("credentials", [COORDINATOR, EVALUATOR, STUDENT])
    def test_other_roles_forbidden(self, client, ai_enabled, credentials):
        login(client, credentials)
        assert client.get("/api/station-guide/status").status_code == 403
        assert _upload(client).status_code == 403
        assert ai_enabled == []

    def test_anonymous_rejected(self, client, ai_enabled):
        assert _upload(client).status_code == 401
        assert client.get("/api/station-guide/jobs/abc").status_code == 401

    def test_job_is_private_to_its_owner(self, client, ai_enabled):
        login(client, ADMIN)
        job_id = _upload(client).json()["job_id"]
        client.post("/api/auth/logout")
        login(client, COEDITOR)
        assert client.get(f"/api/station-guide/jobs/{job_id}").status_code == 404
        assert client.get("/api/station-guide/jobs/no-existe").status_code == 404

    def test_disabled_without_api_key(self, auth_client, monkeypatch):
        monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
        called = []
        monkeypatch.setattr(guide_import, "request_station_suggestions", lambda text: called.append(text))
        assert auth_client.get("/api/station-guide/status").json()["enabled"] is False
        assert _upload(auth_client).status_code == 503
        assert called == []

    def test_invalid_file_rejected_before_calling_the_model(self, auth_client, ai_enabled):
        assert _upload(auth_client, b"no soy un docx", "guia.docx").status_code == 400
        assert _upload(auth_client, b"MZ", "virus.exe").status_code == 400
        assert ai_enabled == []

    def test_oversized_file_rejected(self, auth_client, ai_enabled, monkeypatch):
        monkeypatch.setattr(guide_import, "MAX_GUIDE_SIZE_BYTES", 100)
        assert _upload(auth_client).status_code == 413
        assert ai_enabled == []

    def test_model_failure_is_reported_in_the_job(self, auth_client, ai_enabled, monkeypatch):
        def boom(text):
            raise guide_import.GuideImportError("El asistente de IA no respondió.", 503)

        monkeypatch.setattr(guide_import, "request_station_suggestions", boom)
        job_id = _upload(auth_client).json()["job_id"]
        job = auth_client.get(f"/api/station-guide/jobs/{job_id}").json()
        assert job["status"] == "error" and "no respondió" in job["error"]

    def test_unexpected_failure_does_not_leak_details(self, auth_client, ai_enabled, monkeypatch):
        def boom(text):
            raise RuntimeError("sk-ant-secreto")

        monkeypatch.setattr(guide_import, "request_station_suggestions", boom)
        job_id = _upload(auth_client).json()["job_id"]
        job = auth_client.get(f"/api/station-guide/jobs/{job_id}").json()
        assert job["status"] == "error" and "secreto" not in job["error"]

    def test_too_many_concurrent_jobs(self, auth_client, ai_enabled):
        for _ in range(guide_import.MAX_ACTIVE_JOBS_PER_USER):
            guide_import.create_job(ADMIN[0], "pendiente.docx")
        assert _upload(auth_client).status_code == 429
