from enum import Enum


class RoleCode(str, Enum):
    admin_global = "admin_global"
    miembro = "miembro"
    admin_ecoe = "admin_ecoe"
    coeditor_docente = "coeditor_docente"
    evaluador = "evaluador"
    corrector = "corrector"
    estudiante = "estudiante"
    coordinador_operativo = "coordinador_operativo"
    cronometrador = "cronometrador"


class ECOEStatus(str, Enum):
    borrador = "borrador"
    en_configuracion = "en_configuracion"
    listo_para_pilotaje = "listo_para_pilotaje"
    en_pilotaje = "en_pilotaje"
    pilotaje_validado = "pilotaje_validado"
    publicado = "publicado"
    en_ejecucion = "en_ejecucion"
    cerrado = "cerrado"
    archivado = "archivado"


class StationStatus(str, Enum):
    no_iniciada = "no_iniciada"
    en_diseno = "en_diseno"
    incompleta = "incompleta"
    lista_para_pilotaje = "lista_para_pilotaje"
    en_pilotaje = "en_pilotaje"
    validada = "validada"
    publicada = "publicada"
    activa = "activa"
    finalizada = "finalizada"
    con_incidencia = "con_incidencia"
    cerrada = "cerrada"


class SessionMode(str, Enum):
    pilotaje = "pilotaje"
    ejecucion = "ejecucion"


class InstrumentType(str, Enum):
    checklist = "lista_cotejo"
    rubric = "rubrica_simple"
    scale = "escala_puntaje"
