"""Tester för lagring.py. Sheets-lagret testas mot en låtsasflik, utan nätverk."""
import json

import pytest

import kort as k
import lagring


# ------------------------------------------------------------- JsonLager

def test_json_lager_seedas_med_exempelkort(tmp_path):
    lager = lagring.JsonLager(tmp_path / "kort.json")
    kort = lager.alla()
    assert len(kort) == 5
    assert {x["typ"] for x in kort} == set(k.TYPER)
    assert {x["status"] for x in kort} == set(k.STATUSAR)
    assert all(x["titel"].startswith("EXEMPEL") for x in kort)


def test_json_lager_utan_exempel_ar_tomt(tmp_path):
    assert lagring.JsonLager(tmp_path / "k.json", med_exempel=False).alla() == []


def test_json_lager_lagg_till_uppdatera_ta_bort(tmp_path):
    lager = lagring.JsonLager(tmp_path / "k.json", med_exempel=False)
    kort = k.nytt_kort("Åäö-kort", "Svenska tecken", "jobb")
    lager.lagg_till(kort)
    assert lager.alla() == [kort]
    lager.uppdatera(k.flytta(kort, 1))
    assert lager.alla()[0]["status"] == "påbörjad"
    lager.ta_bort(kort["id"])
    assert lager.alla() == []


def test_json_lager_uppdatera_okant_id_ger_fel(tmp_path):
    lager = lagring.JsonLager(tmp_path / "k.json", med_exempel=False)
    with pytest.raises(lagring.LagerFel):
        lager.uppdatera(k.nytt_kort("X", "", "privat"))


def test_json_lager_andra_falt_ändrar_bara_valda_fält_och_bara_ett_kort(tmp_path):
    lager = lagring.JsonLager(tmp_path / "k.json", med_exempel=False)
    a = {**k.nytt_kort("A", "", "privat"), "förälder_id": "p1", "ordning": "2", "skapad_av": "fjun"}
    b = k.nytt_kort("B", "", "jobb")
    lager.lagg_till(a)
    lager.lagg_till(b)
    ny = lager.andra_falt(a["id"], {"titel": "A2", "slutdatum": "2026-12-01"})
    assert ny["titel"] == "A2"
    kvar_a, kvar_b = lager.alla()
    assert kvar_a == {**a, "titel": "A2", "slutdatum": "2026-12-01"}
    assert kvar_b == b


def test_json_lager_andra_falt_bevarar_det_någon_annan_ändrat_sedan_vi_läste(tmp_path):
    lager = lagring.JsonLager(tmp_path / "k.json", med_exempel=False)
    kort = k.nytt_kort("A", "", "privat")
    lager.lagg_till(kort)
    lager.uppdatera({**kort, "ordning": "7", "status": "påbörjad"})  # t.ex. Fjun
    lager.andra_falt(kort["id"], {"titel": "Ny"})
    assert lager.alla()[0]["ordning"] == "7" and lager.alla()[0]["status"] == "påbörjad"


def test_json_lager_andra_falt_okant_id_och_otillåtna_fält(tmp_path):
    lager = lagring.JsonLager(tmp_path / "k.json", med_exempel=False)
    kort = k.nytt_kort("A", "", "privat")
    lager.lagg_till(kort)
    with pytest.raises(lagring.LagerFel):
        lager.andra_falt("finns-inte", {"titel": "X"})
    with pytest.raises(lagring.LagerFel):
        lager.andra_falt(kort["id"], {"id": "nytt"})
    with pytest.raises(lagring.LagerFel):
        lager.andra_falt(kort["id"], {"påhittat": "x"})
    assert lager.alla() == [kort]


def test_json_lager_ta_bort_flera(tmp_path):
    lager = lagring.JsonLager(tmp_path / "k.json", med_exempel=False)
    kort = [k.nytt_kort(t, "", "privat") for t in "ABC"]
    for x in kort:
        lager.lagg_till(x)
    lager.ta_bort_flera([kort[0]["id"], kort[2]["id"]])
    assert [x["titel"] for x in lager.alla()] == ["B"]


# ------------------------------------------------------------- SheetsLager

class LatsasFlik:
    """Beter sig som det av gspreads Worksheet som SheetsLager använder."""

    def __init__(self, rubriker, rader=()):
        self.rader = [list(rubriker)] + [list(r) for r in rader]
        self.anrop = []

    def row_values(self, n):
        return list(self.rader[n - 1]) if len(self.rader) >= n else []

    def get_all_values(self):
        return [list(r) for r in self.rader]

    def append_row(self, rad, value_input_option=None, table_range=None):
        self.anrop.append(("append", value_input_option))
        self.rader.append(list(rad))

    def update(self, values, range_name, value_input_option=None):
        self.anrop.append(("update", range_name, value_input_option))
        nr = int(range_name.split(":")[0][1:])
        self.rader[nr - 1] = list(values[0])

    def delete_rows(self, nr):
        self.anrop.append(("delete", nr))
        del self.rader[nr - 1]


def rad(**falt):
    return [falt.get(f, "") for f in k.FALT]


def test_sheets_lager_las_alla_hoppar_over_tomma_rader():
    flik = LatsasFlik(k.FALT, [
        rad(id="a", titel="A", status="ny"),
        [""] * len(k.FALT),
        rad(id="b", titel="B", status="påbörjad", förälder_id="a", ordning="2"),
    ])
    kort = lagring.SheetsLager(flik).alla()
    assert [x["id"] for x in kort] == ["a", "b"]
    assert kort[1]["förälder_id"] == "a" and kort[1]["ordning"] == "2"


def test_sheets_lager_korta_rader_fylls_ut():
    flik = LatsasFlik(k.FALT, [["a", "A"]])
    kort = lagring.SheetsLager(flik).alla()
    assert kort[0]["titel"] == "A" and kort[0]["typ"] == ""


def test_sheets_lager_saknad_kolumn_ger_fel():
    flik = LatsasFlik([f for f in k.FALT if f != "typ"])
    with pytest.raises(lagring.LagerFel) as fel:
        lagring.SheetsLager(flik)
    assert "typ" in str(fel.value)


def test_sheets_lager_lagg_till_skriver_raw_i_ratt_ordning():
    flik = LatsasFlik(k.FALT)
    lager = lagring.SheetsLager(flik)
    kort = k.nytt_kort("Ny", "Besk", "jobb", slutdatum="2026-12-01")
    lager.lagg_till(kort)
    assert flik.anrop == [("append", "RAW")]
    assert flik.rader[1] == [kort[f] for f in k.FALT]


def test_sheets_lager_kolumnordning_i_arket_spelar_ingen_roll():
    omvand = list(reversed(k.FALT))
    flik = LatsasFlik(omvand)
    lager = lagring.SheetsLager(flik)
    kort = k.nytt_kort("Ny", "", "privat")
    lager.lagg_till(kort)
    assert lager.alla() == [kort]


def test_sheets_lager_uppdatera_ändrar_bara_rätt_rad_och_bevarar_extra_kolumn():
    rubriker = k.FALT + ["min_extra"]
    flik = LatsasFlik(rubriker, [
        rad(id="a", titel="A", status="ny") + ["spara mig"],
        rad(id="b", titel="B", status="ny") + ["spara mig också"],
    ])
    lager = lagring.SheetsLager(flik)
    b = [x for x in lager.alla() if x["id"] == "b"][0]
    lager.uppdatera(k.flytta(b, 1))
    assert flik.anrop == [("update", "A3:N3", "RAW")]
    assert flik.rader[1][4] == "ny"  # rad A orörd
    assert flik.rader[2][4] == "påbörjad"
    assert flik.rader[2][-1] == "spara mig också"


def test_sheets_lager_uppdatera_okant_id_ger_fel():
    lager = lagring.SheetsLager(LatsasFlik(k.FALT))
    with pytest.raises(lagring.LagerFel):
        lager.uppdatera(k.nytt_kort("X", "", "privat"))


def test_sheets_lager_andra_falt_skriver_en_rad_och_bevarar_övriga_kolumner():
    rubriker = k.FALT + ["min_extra"]
    flik = LatsasFlik(rubriker, [
        rad(id="a", titel="A", status="ny") + ["extra a"],
        rad(id="b", titel="B", status="påbörjad", förälder_id="p1", ordning="3",
            återkommande="varje lördag", skapad_av="fjun", avslutad_datum="2026-10-01",
            beskrivning="gammal") + ["extra b"],
        rad(id="c", titel="C", status="ny") + ["extra c"],
    ])
    före = [list(r) for r in flik.rader]
    lager = lagring.SheetsLager(flik)
    ny = lager.andra_falt("b", {"titel": "B2", "beskrivning": "ny text", "slutdatum": "2026-12-01"})
    assert flik.anrop == [("update", "A3:N3", "RAW")]  # exakt en rad, en skrivning
    assert flik.rader[1] == före[1] and flik.rader[3] == före[3]  # andra rader orörda
    efter = dict(zip(rubriker, flik.rader[2]))
    assert efter["titel"] == "B2" and efter["beskrivning"] == "ny text"
    assert efter["slutdatum"] == "2026-12-01"
    for orord in ("id", "status", "förälder_id", "ordning", "återkommande",
                  "skapad_av", "avslutad_datum", "min_extra"):
        assert efter[orord] == dict(zip(rubriker, före[2]))[orord]
    assert ny["titel"] == "B2" and ny["förälder_id"] == "p1"


def test_sheets_lager_andra_falt_använder_färsk_rad_och_rätt_radnummer():
    flik = LatsasFlik(k.FALT, [rad(id="a", titel="A"), rad(id="b", titel="B")])
    lager = lagring.SheetsLager(flik)
    # Någon (Fjun) lägger in en rad ovanför och ändrar ordning på b efter att appen läste arket
    flik.rader.insert(1, rad(id="x", titel="X"))
    flik.rader[3][k.FALT.index("ordning")] = "9"
    lager.andra_falt("b", {"titel": "B2"})
    assert flik.anrop == [("update", "A4:M4", "RAW")]
    assert flik.rader[3][k.FALT.index("ordning")] == "9"
    assert flik.rader[3][k.FALT.index("titel")] == "B2"


def test_sheets_lager_andra_falt_rör_inte_tom_status_eller_blanksteg_i_andra_kolumner():
    flik = LatsasFlik(k.FALT, [rad(id="a", titel="A", beskrivning="  med blanksteg  ")])
    lagring.SheetsLager(flik).andra_falt("a", {"titel": "A2"})
    assert flik.rader[1][k.FALT.index("status")] == ""
    assert flik.rader[1][k.FALT.index("beskrivning")] == "  med blanksteg  "


def test_sheets_lager_andra_falt_okant_id_och_otillåtna_fält():
    flik = LatsasFlik(k.FALT, [rad(id="a", titel="A")])
    lager = lagring.SheetsLager(flik)
    with pytest.raises(lagring.LagerFel):
        lager.andra_falt("saknas", {"titel": "X"})
    with pytest.raises(lagring.LagerFel):
        lager.andra_falt("a", {"id": "annat"})
    assert flik.anrop == []


def test_sheets_lager_ta_bort_flera_underifran():
    flik = LatsasFlik(k.FALT, [rad(id=str(i), titel=f"T{i}") for i in range(1, 5)])
    lager = lagring.SheetsLager(flik)
    lager.ta_bort_flera(["1", "3"])
    assert [r[0] for r in flik.rader[1:]] == ["2", "4"]
    assert flik.anrop == [("delete", 4), ("delete", 2)]


def test_kolumnbokstav():
    assert lagring._kolumnbokstav(1) == "A"
    assert lagring._kolumnbokstav(13) == "M"
    assert lagring._kolumnbokstav(26) == "Z"
    assert lagring._kolumnbokstav(27) == "AA"


# ------------------------------------------------------------- konfiguration

def test_konfiguration_fran_secrets():
    secrets = {"gcp_service_account": {"client_email": "a@b"}, "ark_id": " abc "}
    assert lagring.las_konfiguration(secrets, {}) == ({"client_email": "a@b"}, "abc")


def test_konfiguration_fran_miljovariabler():
    miljo = {lagring.ENV_NYCKEL: json.dumps({"client_email": "a@b"}), lagring.ENV_ARK_ID: "xyz"}
    assert lagring.las_konfiguration({}, miljo) == ({"client_email": "a@b"}, "xyz")


def test_konfiguration_ogiltig_json_ger_fel():
    with pytest.raises(lagring.LagerFel):
        lagring.las_konfiguration({}, {lagring.ENV_NYCKEL: "{inte json"})


def test_konfiguration_tom():
    assert lagring.las_konfiguration({}, {}) == (None, None)


def test_valj_lager_utan_uppgifter_ar_lokalt(tmp_path):
    lager = lagring.valj_lager({}, {}, fil=tmp_path / "k.json")
    assert isinstance(lager, lagring.JsonLager)


def test_valj_lager_kan_tvingas_lokalt_trots_uppgifter(tmp_path):
    miljo = {lagring.ENV_LAGE: "lokal", lagring.ENV_ARK_ID: "x",
             lagring.ENV_NYCKEL: json.dumps({"a": 1})}
    assert isinstance(lagring.valj_lager({}, miljo, fil=tmp_path / "k.json"), lagring.JsonLager)


def test_valj_lager_med_uppgifter_valjer_sheets(monkeypatch):
    anrop = {}
    monkeypatch.setattr(lagring, "_sheets_lager", lambda n, a: anrop.update(nyckel=n, ark=a) or "SHEETS")
    miljo = {lagring.ENV_ARK_ID: "id1", lagring.ENV_NYCKEL: json.dumps({"a": 1})}
    assert lagring.valj_lager({}, miljo) == "SHEETS"
    assert anrop == {"nyckel": {"a": 1}, "ark": "id1"}


# ------------------------------------------------------------- redigera_kort (båda lagren)

def _lager_json(tmp_path):
    return lagring.JsonLager(tmp_path / "k.json", med_exempel=False)


def _lager_sheets(tmp_path):
    return lagring.SheetsLager(LatsasFlik(k.FALT))


@pytest.fixture(params=[_lager_json, _lager_sheets], ids=["json", "sheets"])
def lager(request, tmp_path):
    return request.param(tmp_path)


def _lagg(lager, **falt):
    kort = {**k.nytt_kort("Original", "Besk", "privat", slutdatum="2026-10-20"),
            "förälder_id": "p1", "ordning": "4", "skapad_av": "fjun", **falt}
    lager.lagg_till(kort)
    return k.normalisera(kort)


def test_redigera_kort_sparar_andringar_och_bevarar_resten(lager):
    kort = _lagg(lager)
    annat = _lagg(lager, id="annat001", titel="Annat kort")
    andringar = lagring.redigera_kort(
        lager, kort, "Ny titel", "Ny besk", "jobb", "Rolf", "2026-10-01", "2026-10-30")
    assert set(andringar) == {"titel", "beskrivning", "typ", "startdatum", "slutdatum"}
    sparat = {x["id"]: x for x in lager.alla()}
    assert sparat[kort["id"]] == {**kort, "titel": "Ny titel", "beskrivning": "Ny besk",
                                  "typ": "jobb", "startdatum": "2026-10-01",
                                  "slutdatum": "2026-10-30"}
    assert sparat[kort["id"]]["förälder_id"] == "p1" and sparat[kort["id"]]["ordning"] == "4"
    assert sparat["annat001"] == annat  # inget annat kort rördes


def test_redigera_kort_ogiltigt_slutdatum_sparar_ingenting(lager):
    kort = _lagg(lager)
    fore = lager.alla()
    with pytest.raises(ValueError, match="Slutdatum"):
        lagring.redigera_kort(lager, kort, "X", "", "privat", "Rolf", "2026-10-10", "2026-10-01")
    assert lager.alla() == fore


def test_redigera_kort_utan_andring_skriver_inget(tmp_path):
    flik = LatsasFlik(k.FALT)
    lager = lagring.SheetsLager(flik)
    kort = _lagg(lager)
    flik.anrop.clear()
    assert lagring.redigera_kort(lager, kort, kort["titel"], kort["beskrivning"], kort["typ"],
                                 kort["ansvarig"], kort["startdatum"], kort["slutdatum"]) == {}
    assert flik.anrop == []


def test_redigera_kort_avslutat_kort_blir_kvar_vid_typbyte(lager):
    kort = _lagg(lager, status="avslutad", avslutad_datum="2026-10-01")
    lagring.redigera_kort(lager, kort, "Original", "Besk", "påminnelse", "Rolf", "", "2026-10-20")
    sparat = lager.alla()[0]
    assert sparat["typ"] == "påminnelse"
    assert sparat["status"] == "avslutad" and sparat["avslutad_datum"] == "2026-10-01"


def test_redigera_kort_nytt_kort_blir_paborjat_vid_byte_till_aterkommande(lager):
    kort = _lagg(lager)
    lagring.redigera_kort(lager, kort, "Original", "Besk", "återkommande", "Rolf", "",
                          "2026-10-20", "varje fredag")
    sparat = lager.alla()[0]
    assert sparat["status"] == "påbörjad" and sparat["återkommande"] == "varje fredag"


def test_redigera_kort_raderat_kort_ger_lagerfel(lager):
    kort = _lagg(lager)
    lager.ta_bort(kort["id"])
    with pytest.raises(lagring.LagerFel):
        lagring.redigera_kort(lager, kort, "Ny", "", "privat", "Rolf")


# ------------------------------------------------------------- flytta med andra_falt (båda lagren)

def test_flytta_skriver_bara_status_och_bevarar_det_andra_ändrat(lager):
    kort = _lagg(lager, status="ny")
    # Efter att appen läste kortet ändrar Fjun andra kolumner på samma rad
    lager.andra_falt(kort["id"], {"ordning": "9", "beskrivning": "Fjuns text", "förälder_id": "p2"})
    lager.andra_falt(kort["id"], k.flytt_andringar(kort, 1))
    sparat = lager.alla()[0]
    assert sparat["status"] == "påbörjad"
    assert sparat["ordning"] == "9" and sparat["beskrivning"] == "Fjuns text"
    assert sparat["förälder_id"] == "p2" and sparat["skapad_av"] == "fjun"


def test_flytta_till_avslutad_och_tillbaka_hanterar_avslutad_datum(lager):
    kort = _lagg(lager, status="påbörjad")
    lager.andra_falt(kort["id"], k.flytt_andringar(kort, 1, idag="2026-10-23"))
    klar = lager.alla()[0]
    assert (klar["status"], klar["avslutad_datum"]) == ("avslutad", "2026-10-23")
    lager.andra_falt(kort["id"], k.flytt_andringar(klar, -1))
    tillbaka = lager.alla()[0]
    assert (tillbaka["status"], tillbaka["avslutad_datum"]) == ("påbörjad", "")


def test_flytta_sheets_skriver_en_rad_och_rör_inte_andra_rader():
    flik = LatsasFlik(k.FALT)
    lager = lagring.SheetsLager(flik)
    a = _lagg(lager, id="aaaa0001", titel="A")
    b = _lagg(lager, id="bbbb0002", titel="B")
    flik.anrop.clear()
    fore_a = list(flik.rader[1])
    lager.andra_falt(b["id"], k.flytt_andringar(b, 1))
    assert flik.anrop == [("update", "A3:M3", "RAW")]
    assert flik.rader[1] == fore_a
    assert flik.rader[2][k.FALT.index("status")] == "påbörjad"
    assert flik.rader[2][k.FALT.index("ordning")] == "4"


def test_regeln_för_typbyte_i_nya_gäller_fortfarande_efter_flytt(lager):
    kort = _lagg(lager, status="ny")
    lagring.redigera_kort(lager, kort, "Original", "Besk", "påminnelse", "Rolf", "", "2026-10-20")
    assert lager.alla()[0]["status"] == "påbörjad"
    assert k.nytt_kort("X", "", "återkommande")["status"] == "påbörjad"
