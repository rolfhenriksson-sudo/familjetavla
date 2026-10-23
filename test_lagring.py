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
