"""Ren logik för Familjetavlan: kort, status, färger och regler.

Här finns inget UI och ingen lagring, bara funktioner som tar emot och
returnerar vanliga dictar. Därför går allt att enhetstesta.

Ett kort är en dict med exakt de nycklar som står i FALT, och alla
värden är text. Det är samma kolumner som i arkets flik "Aktiviteter".
"""
import uuid
from datetime import date, datetime

# Arkets kolumner, i exakt den här ordningen (rubrikraden i fliken "Aktiviteter")
FALT = [
    "id", "titel", "beskrivning", "typ", "status", "ansvarig",
    "startdatum", "slutdatum", "förälder_id", "ordning",
    "återkommande", "skapad_av", "avslutad_datum",
]

# Tavlans tre kolumner, från vänster till höger
STATUSAR = ["ny", "påbörjad", "avslutad"]
STATUS_RUBRIK = {"ny": "Nya", "påbörjad": "Påbörjade", "avslutad": "Avslutade"}

TYPER = ["privat", "påminnelse", "jobb", "återkommande"]

# Dessa typer läggs alltid direkt i Påbörjade
DIREKT_PABORJAD = {"påminnelse", "återkommande"}

# Vilka som kan stå som ansvariga. Fler kan läggas till här senare.
ANVANDARE = ["Rolf"]

# Lugn palett: dämpat salviagrönt, mjukt dimblått, dammrosa, ljus lavendel
FARGER = {
    "privat": {"bakgrund": "#DDE8DC", "kant": "#A8C3A9"},
    "påminnelse": {"bakgrund": "#DCE7F1", "kant": "#A6C0D8"},
    "jobb": {"bakgrund": "#F2DFE1", "kant": "#D9AEB4"},
    "återkommande": {"bakgrund": "#E7E1F3", "kant": "#BDB1DA"},
}
TEXTFARG = "#2F3B35"
OKAND_FARG = {"bakgrund": "#ECECEC", "kant": "#BDBDBD"}

DATUMFORMAT = "%Y-%m-%d"


def farg(typ):
    """Returnerar {'bakgrund': ..., 'kant': ...} för en korttyp."""
    return FARGER.get(typ, OKAND_FARG)


def tolka_datum(text):
    """Gör om 'ÅÅÅÅ-MM-DD' till ett datum. Tom text ger None, felaktig text ValueError."""
    if isinstance(text, datetime):
        return text.date()
    if isinstance(text, date):
        return text
    text = (text or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, DATUMFORMAT).date()
    except ValueError:
        raise ValueError(f"Ogiltigt datum: {text!r} (använd ÅÅÅÅ-MM-DD)") from None


def datum_text(varde):
    """Datum (eller tom text) till 'ÅÅÅÅ-MM-DD' eller tom text."""
    d = tolka_datum(varde)
    return d.strftime(DATUMFORMAT) if d else ""


def normalisera(rad):
    """Gör en rad från lagringen till ett komplett kort.

    Saknade kolumner blir tom text, extra kolumner tas bort och
    alla värden blir text utan extra blanksteg. Okända typer eller
    statusar rörs inte (appen ska inte krascha på ett handskrivet ark),
    men en tom status tolkas som 'ny'.
    """
    kort = {f: ("" if rad.get(f) is None else str(rad.get(f)).strip()) for f in FALT}
    if not kort["status"]:
        kort["status"] = "ny"
    return kort


def nytt_kort(titel, beskrivning="", typ="privat", ansvarig="Rolf",
              startdatum="", slutdatum="", aterkommande="",
              skapad_av="appen"):
    """Skapar ett nytt kort.

    Påminnelser och återkommande kort hamnar direkt i 'påbörjad',
    övriga i 'ny'. Varje gång blir det ett nytt kort med nytt id.
    """
    titel = (titel or "").strip()
    if not titel:
        raise ValueError("Titel får inte vara tom")
    if typ not in TYPER:
        raise ValueError(f"Okänd typ: {typ}")
    start = datum_text(startdatum)
    slut = datum_text(slutdatum)
    if start and slut and slut < start:
        raise ValueError("Slutdatum kan inte ligga före startdatum")
    ansvarig = (ansvarig or "").strip() or ANVANDARE[0]
    kort = {f: "" for f in FALT}
    kort.update({
        "id": uuid.uuid4().hex[:8],
        "titel": titel,
        "beskrivning": (beskrivning or "").strip(),
        "typ": typ,
        "status": "påbörjad" if typ in DIREKT_PABORJAD else "ny",
        "ansvarig": ansvarig,
        "startdatum": start,
        "slutdatum": slut,
        "återkommande": (aterkommande or "").strip() if typ == "återkommande" else "",
        "skapad_av": skapad_av,
    })
    return kort


def flytta(kort, steg, idag=None):
    """Returnerar en kopia av kortet flyttad steg kolumner (-1 vänster, +1 höger).

    Kortet stannar vid kanten. När det hamnar i 'avslutad' sätts
    avslutad_datum, och lämnar det 'avslutad' töms datumet igen.
    """
    if kort["status"] not in STATUSAR:
        raise ValueError(f"Okänd status: {kort['status']}")
    index = STATUSAR.index(kort["status"]) + steg
    index = max(0, min(index, len(STATUSAR) - 1))
    ny_status = STATUSAR[index]
    nytt = {**kort, "status": ny_status}
    if ny_status == "avslutad":
        if kort["status"] != "avslutad":
            nytt["avslutad_datum"] = datum_text(idag or date.today())
    else:
        nytt["avslutad_datum"] = ""
    return nytt


def kan_flytta(kort, steg):
    """True om kortet kan flyttas steg kolumner utan att redan stå vid kanten."""
    if kort["status"] not in STATUSAR:
        return False
    index = STATUSAR.index(kort["status"]) + steg
    return 0 <= index < len(STATUSAR)


def _ordningstal(kort):
    try:
        return float(kort["ordning"])
    except (TypeError, ValueError):
        return float("inf")


def i_status(kortlista, status):
    """Alla kort med en viss status, sorterade efter slutdatum (tomma sist), ordning och titel."""
    urval = [k for k in kortlista if k["status"] == status]
    return sorted(
        urval,
        key=lambda k: (k["slutdatum"] or "9999-99-99", _ordningstal(k), k["titel"].lower()),
    )


def avslutade_id(kortlista):
    """id:n på alla avslutade kort (för 'rensa avslutade')."""
    return [k["id"] for k in kortlista if k["status"] == "avslutad"]


def hitta(kortlista, kort_id):
    """Returnerar kortet med id:t, eller None."""
    for k in kortlista:
        if k["id"] == kort_id:
            return k
    return None
