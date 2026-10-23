"""Enkel lösenordsspärr för appen.

Lösenordet läses ur hemligheten/miljövariabeln APP_LOSENORD (samma mönster som övriga
hemligheter). Är den inte satt körs appen utan lösenordsruta. Ren logik utan Streamlit-anrop,
så att den går att testa direkt.
"""
import hmac
import os

ENV_LOSENORD = "APP_LOSENORD"


def las_losenord(secrets=None, miljo=None):
    """Lösenordet ur Streamlit secrets eller miljövariabeln, eller None om det inte är satt.

    Ett tomt värde (eller bara blanksteg) räknas som "inte satt".
    """
    miljo = miljo if miljo is not None else os.environ
    varde = None
    try:
        if secrets is not None and ENV_LOSENORD in secrets:
            varde = secrets[ENV_LOSENORD]
    except Exception:  # st.secrets kastar fel om ingen secrets-fil finns
        varde = None
    if varde is None:
        varde = miljo.get(ENV_LOSENORD)
    varde = str(varde).strip() if varde is not None else ""
    return varde or None


def losenord_ratt(inmatat, losenord):
    """Jämför i konstant tid. Fel om inget lösenord är konfigurerat eller inget skrivits."""
    if not losenord or inmatat is None:
        return False
    return hmac.compare_digest(str(inmatat).strip().encode("utf-8"), losenord.encode("utf-8"))
