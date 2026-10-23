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


# Fält som kan ändras när man redigerar ett kort. Alla andra kolumner
# (id, status, förälder_id, ordning, skapad_av, avslutad_datum ...) rörs inte.
REDIGERBARA = ["titel", "beskrivning", "typ", "ansvarig",
               "startdatum", "slutdatum", "återkommande"]


def redigera(kort, titel, beskrivning, typ, ansvarig, startdatum="",
             slutdatum="", aterkommande=""):
    """Returnerar en dict med BARA de fält som ändras när kortet redigeras.

    Tom dict betyder att inget ändrades. Regler:
      - titel får inte vara tom, typen måste vara känd och slutdatum
        får inte ligga före startdatum (ValueError med svenskt meddelande)
      - status och avslutad_datum ändras aldrig, utom att ett kort i 'ny'
        som byter typ till påminnelse eller återkommande flyttas till
        'påbörjad' (samma regel som för nya kort). Ett kort som redan är
        påbörjat eller avslutat blir kvar där det är.
      - 'återkommande'-texten ändras bara när typen är återkommande;
        annars lämnas den som den är
    """
    titel = (titel or "").strip()
    if not titel:
        raise ValueError("Titel får inte vara tom")
    typ = (typ or "").strip()
    if typ not in TYPER and typ != kort["typ"]:  # en redan okänd typ i arket får vara kvar
        raise ValueError(f"Okänd typ: {typ}")
    start = datum_text(startdatum)
    slut = datum_text(slutdatum)
    if start and slut and slut < start:
        raise ValueError("Slutdatum kan inte ligga före startdatum")
    nya = {
        "titel": titel,
        "beskrivning": (beskrivning or "").strip(),
        "typ": typ,
        "ansvarig": (ansvarig or "").strip() or ANVANDARE[0],
        "startdatum": start,
        "slutdatum": slut,
    }
    if typ == "återkommande":
        nya["återkommande"] = (aterkommande or "").strip()
    if kort["status"] == "ny" and typ != kort["typ"] and typ in DIREKT_PABORJAD:
        nya["status"] = "påbörjad"
    return {falt: varde for falt, varde in nya.items() if kort.get(falt, "") != varde}


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


def flytt_andringar(kort, steg, idag=None):
    """Bara de fält som ändras när kortet flyttas (status, ev. avslutad_datum).

    Tom dict om kortet redan står vid kanten. Används med lager.andra_falt så att
    inga andra kolumner skrivs när ett kort flyttas.
    """
    flyttat = flytta(kort, steg, idag)
    return {f: v for f, v in flyttat.items() if kort.get(f, "") != v}


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
    """id:n som tas bort av 'rensa avslutade'.

    Det är de avslutade korten på tavlan (vanliga kort och projekt) samt alla pass
    som hör till de avslutade projekten. Avslutade pass i ett projekt som
    inte är klart rensas aldrig.
    """
    ids = []
    for kort in tavelkort(kortlista):
        if kort["status"] == "avslutad":
            ids += [p["id"] for p in passen_till(kortlista, kort["id"])]
            ids.append(kort["id"])
    return ids


def hitta(kortlista, kort_id):
    """Returnerar kortet med id:t, eller None."""
    for k in kortlista:
        if k["id"] == kort_id:
            return k
    return None


# ---------------------------------------------------------------- projekt och pass
#
# Ett pass är ett kort vars förälder_id pekar på ett annat kort (projektet).
# Ett projekt är ett kort som har minst ett pass. Passen visas inte som egna
# kort på tavlan, och projektets status följer passen.


def ar_pass(kort):
    """True om kortet har ett förälder_id (oavsett om föräldern finns)."""
    return bool(kort["förälder_id"])


def _giltiga_projekt(kortlista):
    """{id: kort} för kort som kan vara förälder: de är inte själva pass."""
    return {x["id"]: x for x in kortlista if x["id"] and not ar_pass(x)}


def ar_foraldralost(kort, kortlista):
    """True om kortet är ett pass vars förälder saknas eller inte kan vara förälder.

    Det gäller när föräldern är borttagen, när kortet pekar på sig själv eller
    när föräldern själv är ett pass. Sådana kort behandlas som vanliga kort
    så att de aldrig försvinner från tavlan.
    """
    return ar_pass(kort) and kort["förälder_id"] not in _giltiga_projekt(kortlista)


def tavelkort(kortlista):
    """De kort som visas på tavlan: vanliga kort, projekt och föräldralösa pass."""
    giltiga = _giltiga_projekt(kortlista)
    return [x for x in kortlista if not ar_pass(x) or x["förälder_id"] not in giltiga]


def passen_till(kortlista, projekt_id):
    """Projektets pass i ordning (ordning 1, 2, 3 ...).

    Pass utan tal i ordning hamnar sist, och pass med samma ordning behåller
    den inbördes ordning de har i arket. Tom lista om projekt_id inte är ett
    giltigt projekt (alltså inte själv ett pass).
    """
    if not projekt_id or projekt_id not in _giltiga_projekt(kortlista):
        return []
    pass_ = [x for x in kortlista if x["förälder_id"] == projekt_id and x["id"] != projekt_id]
    return sorted(pass_, key=_ordningstal)  # sorted är stabil


def ar_projekt(kort, kortlista):
    """True om kortet är ett projekt, alltså har minst ett pass."""
    return not ar_pass(kort) and bool(passen_till(kortlista, kort["id"]))


def framsteg(pass_lista):
    """(klara, totalt) för en lista pass."""
    return sum(1 for p in pass_lista if p["status"] == "avslutad"), len(pass_lista)


def framsteg_text(pass_lista):
    klara, totalt = framsteg(pass_lista)
    return f"{klara} av {totalt} pass klara"


def projektstatus(pass_lista, typ=""):
    """Projektets status utifrån passen, eller None om det inte finns några pass.

    Inget pass påbörjat eller avslutat -> 'ny'. Minst ett påbörjat eller avslutat
    men inte alla avslutade -> 'påbörjad'. Alla avslutade -> 'avslutad'.
    Ett pass med okänd status räknas som 'ny'.
    Påminnelser och återkommande projekt står aldrig i 'ny' (samma regel som
    för vanliga kort), utan i 'påbörjad' tills alla pass är klara.
    """
    if not pass_lista:
        return None
    statusar = [p["status"] for p in pass_lista]
    if all(s == "avslutad" for s in statusar):
        return "avslutad"
    if any(s in ("påbörjad", "avslutad") for s in statusar) or typ in DIREKT_PABORJAD:
        return "påbörjad"
    return "ny"


def status_andringar(kort, ny_status, idag=None):
    """Bara de fält som ändras när kortet får en ny status (status, avslutad_datum).

    avslutad_datum sätts när kortet blir avslutat och töms när det lämnar
    'avslutad'. Tom dict om statusen redan stämmer.
    """
    if ny_status not in STATUSAR:
        raise ValueError(f"Okänd status: {ny_status}")
    nya = {"status": ny_status}
    if ny_status == "avslutad":
        if kort["status"] != "avslutad":
            nya["avslutad_datum"] = datum_text(idag or date.today())
    else:
        nya["avslutad_datum"] = ""
    return {f: v for f, v in nya.items() if kort.get(f, "") != v}


def projekt_andringar(projekt, pass_lista, idag=None):
    """Fälten som ska skrivas på projektkortet så att statusen följer passen."""
    ny_status = projektstatus(pass_lista, projekt["typ"])
    if ny_status is None or ny_status == projekt["status"]:
        return {}
    return status_andringar(projekt, ny_status, idag)


def nytt_pass(projekt, titel, beskrivning="", startdatum="", slutdatum="",
              ordning=1, skapad_av="appen"):
    """Skapar ett nytt pass i projektet. Typ och ansvarig ärvs från projektet."""
    pass_ = nytt_kort(titel, beskrivning, projekt["typ"] if projekt["typ"] in TYPER else "privat",
                      projekt["ansvarig"], startdatum, slutdatum, "", skapad_av)
    pass_.update({
        "typ": projekt["typ"],
        "status": "ny",
        "förälder_id": projekt["id"],
        "ordning": str(ordning),
    })
    return pass_


def ordningsandringar(ordnade_id, pass_lista):
    """{id: {'ordning': 'n'}} för de pass vars ordning inte redan är 1, 2, 3 ... i angiven följd."""
    nu = {p["id"]: p["ordning"] for p in pass_lista}
    return {i: {"ordning": str(n)} for n, i in enumerate(ordnade_id, start=1)
            if i in nu and nu[i] != str(n)}


def pass_efter_infogning(pass_lista, fore_id=None):
    """Planerar ett nytt pass: (ordning för det nya, ändringar för de gamla).

    Det nya passet läggs först före passet fore_id, eller sist om fore_id är None
    eller okänt. De gamla passen numreras om till 1, 2, 3 ... men bara de vars
    ordning faktiskt ändras tas med.
    """
    sorterade = sorted(pass_lista, key=_ordningstal)
    ordnade = [p["id"] for p in sorterade]
    plats = ordnade.index(fore_id) if fore_id in ordnade else len(ordnade)
    # Det nya passet får platsen plats+1. De som står efter skjuts ett steg.
    ordnat_med_lucka = ordnade[:plats] + [None] + ordnade[plats:]
    andringar = {}
    nu = {p["id"]: p["ordning"] for p in sorterade}
    for n, i in enumerate(ordnat_med_lucka, start=1):
        if i is not None and nu[i] != str(n):
            andringar[i] = {"ordning": str(n)}
    return plats + 1, andringar


def flytta_pass(pass_lista, pass_id, steg):
    """Ändringar av ordning när ett pass flyttas steg platser (-1 upp, +1 ned).

    Tom dict om passet redan står vid kanten eller inte finns. Hela listan
    numreras om till 1, 2, 3 ..., men bara de pass vars ordning ändras tas med.
    """
    sorterade = sorted(pass_lista, key=_ordningstal)
    ordnade = [p["id"] for p in sorterade]
    if pass_id not in ordnade:
        return {}
    nu = ordnade.index(pass_id)
    mal = nu + steg
    if not 0 <= mal < len(ordnade):
        return {}
    ordnade[nu], ordnade[mal] = ordnade[mal], ordnade[nu]
    return ordningsandringar(ordnade, sorterade)
