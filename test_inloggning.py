"""Tester för lösenordsspärren: logiken och appen med och utan APP_LOSENORD.

Alla lösenord här är påhittade testvärden.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import inloggning
import lagring

TEST_LOSEN = "testlosen-123"


# ---------------------------------------------------------------- logik


def test_losenord_fran_secrets():
    assert inloggning.las_losenord({"APP_LOSENORD": TEST_LOSEN}, {}) == TEST_LOSEN


def test_losenord_fran_miljovariabel():
    assert inloggning.las_losenord({}, {"APP_LOSENORD": TEST_LOSEN}) == TEST_LOSEN
    assert inloggning.las_losenord(None, {"APP_LOSENORD": TEST_LOSEN}) == TEST_LOSEN


def test_secrets_gar_fore_miljovariabel():
    assert inloggning.las_losenord({"APP_LOSENORD": "a-test"}, {"APP_LOSENORD": "b-test"}) == "a-test"


@pytest.mark.parametrize("varde", [None, "", "   ", "\n"])
def test_tomt_eller_saknat_losenord_ar_inte_satt(varde):
    miljo = {} if varde is None else {"APP_LOSENORD": varde}
    assert inloggning.las_losenord({}, miljo) is None


def test_secrets_som_kastar_fel_ignoreras():
    class Trasig:
        def __contains__(self, nyckel):
            raise FileNotFoundError("ingen secrets-fil")

    assert inloggning.las_losenord(Trasig(), {}) is None
    assert inloggning.las_losenord(Trasig(), {"APP_LOSENORD": TEST_LOSEN}) == TEST_LOSEN


def test_siffror_i_toml_blir_text():
    assert inloggning.las_losenord({"APP_LOSENORD": 1234}, {}) == "1234"


def test_ratt_losenord():
    assert inloggning.losenord_ratt(TEST_LOSEN, TEST_LOSEN)
    assert inloggning.losenord_ratt(f"  {TEST_LOSEN} ", TEST_LOSEN)
    assert inloggning.losenord_ratt("åäö-test", "åäö-test")  # icke-ASCII klarar compare_digest


@pytest.mark.parametrize("inmatat", ["", "fel", TEST_LOSEN.upper(), TEST_LOSEN + "x", None])
def test_fel_losenord(inmatat):
    assert not inloggning.losenord_ratt(inmatat, TEST_LOSEN)


@pytest.mark.parametrize("losenord", [None, ""])
def test_aldrig_inloggad_utan_konfigurerat_losenord(losenord):
    assert not inloggning.losenord_ratt("", losenord)
    assert not inloggning.losenord_ratt("x", losenord)


def test_ar_sheets_lage(monkeypatch):
    nyckel = json.dumps({"type": "service_account"})
    assert not lagring.ar_sheets_lage({}, {})
    assert not lagring.ar_sheets_lage({}, {"GOOGLE_SERVICE_ACCOUNT_JSON": nyckel})  # ark-id saknas
    miljo = {"GOOGLE_SERVICE_ACCOUNT_JSON": nyckel, "FAMILJETAVLA_ARK_ID": "ark"}
    assert lagring.ar_sheets_lage({}, miljo)
    assert not lagring.ar_sheets_lage({}, {**miljo, "FAMILJETAVLA_LAGE": "lokal"})
    assert lagring.ar_sheets_lage({}, {**miljo, "GOOGLE_SERVICE_ACCOUNT_JSON": "{trasig"})


# ---------------------------------------------------------------- appen


@pytest.fixture
def miljo(tmp_path, monkeypatch):
    monkeypatch.setenv("FAMILJETAVLA_LAGE", "lokal")
    monkeypatch.setenv("FAMILJETAVLA_FIL", str(tmp_path / "kort.json"))
    monkeypatch.delenv("APP_LOSENORD", raising=False)
    st.cache_resource.clear()
    return monkeypatch


def starta():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def logga_in(at, losen):
    at.text_input[0].set_value(losen)
    at.button[0].click().run()
    assert not at.exception
    return at


def ar_tavlan(at):
    return [h.value for h in at.header] == ["Nya (1)", "Påbörjade (3)", "Avslutade (1)"]


def test_utan_losenord_ingen_ruta_och_tavlan_syns(miljo):
    at = starta()
    assert ar_tavlan(at)
    assert not any(t.label == "Lösenord" for t in at.text_input)
    assert not any(w.value.startswith("⚠️") for w in at.caption)  # lokalt läge: ingen varning


def test_med_losenord_visas_bara_rutan(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    at = starta()
    assert len(at.text_input) == 1
    assert at.text_input[0].label == "Lösenord"
    assert at.text_input[0].proto.type == 1  # PASSWORD
    assert not at.header and not at.expander and len(at.button) == 1
    assert not at.error


def test_inget_lager_startas_fore_inloggning(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    anrop = []
    original = lagring.valj_lager
    miljo.setattr(lagring, "valj_lager", lambda *a, **kw: anrop.append(1) or original(*a, **kw))
    at = starta()
    at.text_input[0].set_value("fel").run()
    at.button[0].click().run()
    assert anrop == []
    assert not Path(os.environ["FAMILJETAVLA_FIL"]).exists()  # ingen datafil skapades heller
    logga_in(at, TEST_LOSEN)
    assert anrop == [1]


def test_fel_losenord_ger_fel_och_ingen_tavla(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    at = logga_in(starta(), "fel-test")
    assert [e.value for e in at.error] == ["Fel lösenord."]
    assert not at.header
    assert "inloggad" not in at.session_state


def test_ratt_losenord_visar_tavlan_och_sparas_i_sessionen(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    at = logga_in(starta(), TEST_LOSEN)
    assert ar_tavlan(at)
    assert at.session_state["inloggad"] is True
    assert not any(t.label == "Lösenord" for t in at.text_input)
    # Inloggningen består över nya körningar i samma session
    at.run()
    assert ar_tavlan(at) and not at.error


def test_tavlan_fungerar_efter_inloggning(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    at = logga_in(starta(), TEST_LOSEN)
    [b for b in at.button if b.key == "h_ex000001"][0].click().run()
    assert not at.exception
    assert [h.value for h in at.header] == ["Nya (0)", "Påbörjade (4)", "Avslutade (1)"]


def test_ny_session_maste_logga_in_igen(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    logga_in(starta(), TEST_LOSEN)
    ny = starta()
    assert not ny.header and len(ny.text_input) == 1


def test_inloggad_flagga_i_sessionen_racker_inte_om_den_inte_ar_true(miljo):
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["inloggad"] = "ja"
    at.run()
    assert not at.header and len(at.text_input) == 1


def test_tomt_losenord_i_miljon_ger_ingen_ruta(miljo):
    miljo.setenv("APP_LOSENORD", "")
    assert ar_tavlan(starta())


def test_varning_i_sheets_lage_utan_losenord(miljo):
    miljo.delenv("FAMILJETAVLA_LAGE")
    miljo.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps({"type": "service_account"}))
    miljo.setenv("FAMILJETAVLA_ARK_ID", "test-ark")
    # Ersätter bara anslutningen, så ingen riktig Sheets-åtkomst sker
    miljo.setattr(lagring, "_sheets_lager", lambda nyckel, ark_id: _tomt_lager())
    at = starta()
    assert any("Ingen lösenordsskydd är aktivt" in c.value for c in at.caption)


def test_ingen_varning_i_sheets_lage_med_losenord(miljo):
    miljo.delenv("FAMILJETAVLA_LAGE")
    miljo.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", json.dumps({"type": "service_account"}))
    miljo.setenv("FAMILJETAVLA_ARK_ID", "test-ark")
    miljo.setenv("APP_LOSENORD", TEST_LOSEN)
    miljo.setattr(lagring, "_sheets_lager", lambda nyckel, ark_id: _tomt_lager())
    at = starta()
    assert not any("lösenordsskydd" in c.value for c in at.caption)
    logga_in(at, TEST_LOSEN)
    assert not any("lösenordsskydd" in c.value for c in at.caption)


def _tomt_lager():
    return lagring.JsonLager(tempfile.mkdtemp() + "/kort.json")
