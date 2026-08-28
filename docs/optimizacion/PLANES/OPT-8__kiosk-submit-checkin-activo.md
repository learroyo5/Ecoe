# OPT-8 · `/kiosk/submit` debe exigir el check-in confirmado vigente

**Severidad: baja (integridad de dato / permiso).** Origen: H-vivo-5.

## Problema

Con un token de kiosko válido para la estación X, una request armada a mano a `POST /api/kiosk/submit` puede
enviar respuestas atribuidas a **cualquier estudiante que haya tenido un check-in en X** cuya ventana de tiempo
siga abierta (p. ej. el estudiante inmediatamente anterior durante el solapamiento de la transición), mientras
ese estudiante aún no tenga respuesta registrada.

## Causa raíz

`app/api/routes/kiosk.py::kiosk_submit` hace `checkin = db.get(StationCheckIn, payload.checkin_id)` y solo
valida `checkin.station_id == kiosk.station_id`. No exige que sea el check-in `confirmado` vigente de la
estación. El comentario del código ("identity is fixed by the check-in row, so nothing can be submitted on
someone else's behalf") subestima este borde.

## Cambio propuesto

- **Backend** (`app/api/routes/kiosk.py::kiosk_submit`): tras resolver el `checkin`, exigir que sea el check-in
  `confirmado` más reciente de la estación:
  ```python
  active = db.scalar(
      select(StationCheckIn)
      .where(StationCheckIn.station_id == kiosk.station_id,
             StationCheckIn.status == "confirmado")
      .order_by(StationCheckIn.confirmed_at.desc(), StationCheckIn.id.desc())
  )
  if not active or active.id != payload.checkin_id:
      raise HTTPException(status_code=409, detail="No hay un ingreso activo para esta estación")
  ```
  (Verificar la interacción con `confirm_station_checkin`, que ya cierra los `confirmado` previos de la
  estación — tras esa lógica solo debería haber uno activo a la vez.)
- **Frontend**: ninguno (el kiosko ya envía el `checkin_id` que le da `/kiosk/context`, que es el activo).
- **Migración**: no.
- **Máquina de estados**: no.

## Tests (negativos obligatorios — permiso/integridad)

- `test_kiosk_submit_rejects_previous_checkin` (negativo) — estación con check-in A (cerrado) y B (activo);
  `POST /kiosk/submit` con `checkin_id = A` → 409, sin `StudentResponse` creada para A.
- `test_kiosk_submit_accepts_active_checkin` — con `checkin_id = B` → 200.
- `test_kiosk_submit_rejects_checkin_of_other_station` (regresión del check ya existente) → sigue 4xx.
- `test_kiosk_submit_after_rotation` — tras confirmar un nuevo check-in, el anterior deja de aceptar envíos.

## Riesgos / alcance

- Riesgo de romper un caso legítimo de "envío tardío del estudiante correcto" si la rotación ya avanzó y su
  check-in dejó de ser el más reciente. Hoy eso se resuelve por contingencia de todos modos
  (`docs/OPERACION_DIA_EXAMEN.md`); confirmar con el usuario que el kiosko **no** debe aceptar envíos de un
  estudiante cuya rotación ya cerró (comportamiento esperado: sí debe rechazarlos, van por contingencia).
- Commit muy acotado: una guarda en un endpoint + 4 tests.

## Verificación

- [ ] `cd backend && python3 -m pytest tests/test_kiosk*.py -v`
- [ ] `cd backend && python3 -m pytest`

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ✅ 2026-08-28 (parte del lote de estabilización Grupo A)
