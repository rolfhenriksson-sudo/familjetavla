"""Lagring för Familjetavlan.

Två lager med samma gränssnitt (Lager):
  - JsonLager:   en lokal JSON-fil, för demo och tester. Kräver ingen inloggning.
  - SheetsLager: Google Sheets, fliken "Aktiviteter". Delas med Fänrik Fjun.

Lagren ändrar bara en rad i taget (lägg till, uppdatera, ta bort) i stället för
att skriva om hela arket. Då skriver vi inte över det Fjun har lagt in
under tiden.
"""
import json
import os
from pathlib import Path

import kort as k

FLIK = "Aktiviteter"
ENV_ARK_ID = "FAMILJETAVLA_ARK_ID"
ENV_NYCKEL = "GOOGLE_SERVICE_ACCOUNT_JSON"
ENV_LAGE = "FAMILJETAVLA_LAGE"  # "lokal" tvingar lokalt läge
ENV_FIL = "FAMILJETAVLA_FIL"


class LagerFel(Exception):
    """Fel med lagringen, med ett förklarande meddelande på svenska."""


class Lager:
    """Gränssnittet som appen använder. Alla kort är dictar enligt kort.FALT."""

    beskrivning = ""

    def alla(self):
        raise NotImplementedError

    def lagg_till(self, kort):
        raise NotImplementedError

    def uppdatera(self, kort):
        """Skriver över kortet som har samma id."""
        raise NotImplementedError

    def ta_bort(self, kort_id):
        raise NotImplementedError

    def ta_bort_flera(self, id_lista):
        for kort_id in id_lista:
            self.ta_bort(kort_id)


# ---------------------------------------------------------------- lokalt lager

def exempelkort():
    """Tydligt märkta exempelkort, ett per typ, för demo och första test."""
    def kort(id_, titel, besk, typ, status, start="", slut="", aterk="", klar=""):
        return {**{f: "" for f in k.FALT}, "id": id_, "titel": titel,
                "beskrivning": besk, "typ": typ, "status": status,
                "ansvarig": "Rolf", "startdatum": start, "slutdatum": slut,
                "återkommande": aterk, "skapad_av": "exempel",
                "avslutad_datum": klar}
    return [
        kort("ex000001", "EXEMPEL: Rensa värmepumpsfiltret",
             "Exempelkort (privat, ny). Kan tas bort.", "privat", "ny",
             slut="2026-10-25"),
        kort("ex000002", "EXEMPEL: Boka möte med Jon",
             "Exempelkort (påminnelse, påbörjad). Kan tas bort.", "påminnelse",
             "påbörjad", "2026-10-23", "2026-11-10"),
        kort("ex000003", "EXEMPEL: Förbereda kvartalsmöte",
             "Exempelkort (jobb, påbörjad). Kan tas bort.", "jobb", "påbörjad",
             "2026-10-20", "2026-10-30"),
        kort("ex000004", "EXEMPEL: Ring Peter eller Zacka",
             "Exempelkort (återkommande, påbörjad). Kan tas bort.", "återkommande",
             "påbörjad", "2026-10-24", "2026-10-24", "varje lördag"),
        kort("ex000005", "EXEMPEL: Måla hallväggen",
             "Exempelkort (privat, avslutad). Kan tas bort.", "privat", "avslutad",
             "2026-10-10", "2026-10-18", klar="2026-10-18"),
    ]


class JsonLager(Lager):
    """Sparar korten i en JSON-fil. Finns ingen fil skapas den med exempelkort."""

    def __init__(self, fil="kort.json", med_exempel=True):
        self.fil = Path(fil)
        self.beskrivning = f"Lokalt läge (demo): korten sparas i {self.fil.name}"
        if med_exempel and not self.fil.exists():
            self._skriv(exempelkort())

    def _las(self):
        if not self.fil.exists():
            return []
        return [k.normalisera(r) for r in json.loads(self.fil.read_text(encoding="utf-8"))]

    def _skriv(self, kortlista):
        self.fil.write_text(
            json.dumps(kortlista, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def alla(self):
        return self._las()

    def lagg_till(self, kort):
        self._skriv(self._las() + [k.normalisera(kort)])

    def uppdatera(self, kort):
        kortlista = self._las()
        if not any(x["id"] == kort["id"] for x in kortlista):
            raise LagerFel(f"Hittar inget kort med id {kort['id']}")
        self._skriv([k.normalisera(kort) if x["id"] == kort["id"] else x for x in kortlista])

    def ta_bort(self, kort_id):
        self._skriv([x for x in self._las() if x["id"] != kort_id])


# ---------------------------------------------------------------- Sheets-lager

class SheetsLager(Lager):
    """Läser och skriver fliken 'Aktiviteter' i ett Google Sheet.

    `flik` är ett gspread-Worksheet (eller något som beter sig likadant,
    det används i testerna). Kolumnerna hittas via rubrikraden, så
    ordningen i arket spelar ingen roll och extra kolumner bevaras.
    """

    def __init__(self, flik, beskrivning="Ansluten till Google Sheets"):
        self.flik = flik
        self.beskrivning = beskrivning
        self.rubriker = self._las_rubriker()

    def _las_rubriker(self):
        rubriker = [r.strip() for r in self.flik.row_values(1)]
        saknas = [f for f in k.FALT if f not in rubriker]
        if saknas:
            raise LagerFel(
                "Fliken 'Aktiviteter' saknar kolumnerna: " + ", ".join(saknas)
                + ". Rubrikraden måste innehålla: " + ", ".join(k.FALT)
            )
        return rubriker

    def _rader(self):
        """Alla datarader som (radnummer i arket, dict). Tomma rader hoppas över."""
        varden = self.flik.get_all_values()
        resultat = []
        for nr, rad in enumerate(varden[1:], start=2):
            rad = list(rad) + [""] * (len(self.rubriker) - len(rad))
            post = dict(zip(self.rubriker, rad))
            if not post.get("id", "").strip() and not post.get("titel", "").strip():
                continue
            resultat.append((nr, post))
        return resultat

    def alla(self):
        return [k.normalisera(post) for _, post in self._rader()]

    def _hitta_rad(self, kort_id):
        """(radnummer, rad som dict) för kortet. Läser arket på nytt varje gång."""
        for nr, post in self._rader():
            if post.get("id", "").strip() == kort_id:
                return nr, post
        raise LagerFel(f"Hittar inget kort med id {kort_id} i arket (har någon tagit bort det?)")

    def _radnummer(self, kort_id):
        return self._hitta_rad(kort_id)[0]

    def _som_rad(self, kort, gammal=None):
        kort = k.normalisera(kort)
        rad = []
        for rubrik in self.rubriker:
            if rubrik in kort:
                rad.append(kort[rubrik])
            else:  # okänd extra kolumn: behåll det som stod där
                rad.append((gammal or {}).get(rubrik, ""))
        return rad

    def lagg_till(self, kort):
        # RAW: texten (t.ex. datum) sparas som den är, utan omformatering
        self.flik.append_row(
            self._som_rad(kort), value_input_option="RAW", table_range="A1"
        )

    def uppdatera(self, kort):
        nr, gammal = self._hitta_rad(kort["id"])
        rad = self._som_rad(kort, gammal)
        slut = _kolumnbokstav(len(self.rubriker))
        self.flik.update(
            values=[rad], range_name=f"A{nr}:{slut}{nr}", value_input_option="RAW"
        )

    def ta_bort(self, kort_id):
        self.flik.delete_rows(self._radnummer(kort_id))

    def ta_bort_flera(self, id_lista):
        # Underifrån och upp, så att radnumren inte förskjuts
        rader = sorted((self._radnummer(i) for i in id_lista), reverse=True)
        for nr in rader:
            self.flik.delete_rows(nr)


def _kolumnbokstav(antal):
    """1 -> A, 13 -> M, 27 -> AA."""
    bokstav = ""
    while antal:
        antal, rest = divmod(antal - 1, 26)
        bokstav = chr(65 + rest) + bokstav
    return bokstav


# ---------------------------------------------------------------- val av lager

def las_konfiguration(secrets=None, miljo=None):
    """Hämtar (nyckel, ark_id) ur Streamlit secrets eller miljövariabler.

    `secrets` är en dict-liknande (st.secrets), `miljo` är os.environ.
    nyckel är service account-uppgifterna som dict, eller None.
    """
    secrets = secrets if secrets is not None else {}
    miljo = miljo if miljo is not None else os.environ
    nyckel = None
    try:
        if "gcp_service_account" in secrets:
            nyckel = dict(secrets["gcp_service_account"])
    except Exception:  # st.secrets kastar fel om ingen secrets-fil finns
        nyckel = None
    if nyckel is None and miljo.get(ENV_NYCKEL):
        try:
            nyckel = json.loads(miljo[ENV_NYCKEL])
        except json.JSONDecodeError:
            raise LagerFel(
                f"{ENV_NYCKEL} innehåller inte giltig JSON. "
                "Klistra in hela nyckelfilen från Google."
            ) from None
    ark_id = None
    try:
        if "ark_id" in secrets:
            ark_id = str(secrets["ark_id"]).strip()
    except Exception:
        ark_id = None
    ark_id = ark_id or (miljo.get(ENV_ARK_ID) or "").strip() or None
    return nyckel, ark_id


def valj_lager(secrets=None, miljo=None, fil=None):
    """Sheets-lager om uppgifterna finns, annars lokalt lager.

    Sätt FAMILJETAVLA_LAGE=lokal för att tvinga fram lokalt läge.
    """
    miljo = miljo if miljo is not None else os.environ
    fil = fil or miljo.get(ENV_FIL) or "kort.json"
    if (miljo.get(ENV_LAGE) or "").lower() == "lokal":
        return JsonLager(fil)
    nyckel, ark_id = las_konfiguration(secrets, miljo)
    if not (nyckel and ark_id):
        return JsonLager(fil)
    return _sheets_lager(nyckel, ark_id)


def _sheets_lager(nyckel, ark_id):
    import gspread  # importeras här så lokalt läge inte kräver Google-paket

    try:
        klient = gspread.service_account_from_dict(nyckel)
        ark = klient.open_by_key(ark_id)
        return SheetsLager(ark.worksheet(FLIK))
    except LagerFel:
        raise
    except gspread.exceptions.SpreadsheetNotFound:
        raise LagerFel(
            "Hittar inte arket. Kontrollera ark-id:t och att arket är delat "
            "med service accountens e-postadress (redigerare)."
        ) from None
    except gspread.exceptions.WorksheetNotFound:
        raise LagerFel(f"Arket saknar fliken '{FLIK}'.") from None
    except gspread.exceptions.APIError as fel:
        raise LagerFel(f"Google svarade med ett fel: {fel}") from None
