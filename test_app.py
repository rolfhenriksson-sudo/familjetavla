"""Rökprov: appen startar i lokalt läge utan inloggning och klarar grundflödena."""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import kort as k


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("FAMILJETAVLA_LAGE", "lokal")
    monkeypatch.delenv("APP_LOSENORD", raising=False)  # testerna ska inte påverkas av ens egen miljö
    monkeypatch.setenv("FAMILJETAVLA_FIL", str(tmp_path / "kort.json"))
    st.cache_resource.clear()  # appen cachar lagret, och varje test ska ha sitt eget
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_startar_i_lokalt_lage_med_exempelkort(app):
    assert "Lokalt läge" in app.caption[0].value
    rubriker = [h.value for h in app.header]
    assert rubriker == ["Nya (1)", "Påbörjade (3)", "Avslutade (1)"]


def test_flytta_kort_med_knapp(app):
    # Det nya kortet "Rensa värmepumpsfiltret" har id ex000001
    knapp = [b for b in app.button if b.key == "h_ex000001"][0]
    knapp.click().run()
    assert not app.exception
    assert [h.value for h in app.header] == ["Nya (0)", "Påbörjade (4)", "Avslutade (1)"]


def test_lagg_till_kort(app):
    app.text_input[0].set_value("Köpa blommor")
    app.selectbox[0].select("påminnelse")
    app.button[0].click().run()  # första knappen är formulärets "Lägg till"
    assert not app.exception
    assert [h.value for h in app.header][1] == "Påbörjade (4)"


def test_tom_titel_ger_varning(app):
    app.button[0].click().run()
    assert any("Titel" in w.value for w in app.warning)


def _oppna_redigera(app, kort_id):
    [b for b in app.button if b.key == f"e_{kort_id}"][0].click().run()
    assert not app.exception


def _i_dialogen(widgets):
    """Bara reglagen i redigeringsdialogen (inte formuläret 'Nytt kort')."""
    return [w for w in widgets if (w.form_id or "").startswith("redigera_")]


def _spara_knapp(app):
    return [b for b in app.button if b.label == "Spara"][0]


# Obs: själva "Spara" i dialogen körs som ett fragment i webbläsaren, vilket
# AppTest inte kan återskapa. Sparlogiken testas därför i test_kort.py och
# test_lagring.py (lagring.redigera_kort mot båda lagren).


def test_redigera_dialogen_visar_kortets_nuvarande_varden(app):
    _oppna_redigera(app, "ex000004")  # återkommande kort med start- och slutdatum
    titel = [t for t in _i_dialogen(app.text_input) if t.label == "Titel"][0]
    assert titel.value == "EXEMPEL: Ring Peter eller Zacka"
    typ = [s for s in _i_dialogen(app.selectbox) if s.label == "Typ"][0]
    assert typ.value == "återkommande"
    start, slut = _i_dialogen(app.date_input)
    assert str(start.value) == "2026-10-24" and str(slut.value) == "2026-10-24"
    assert [t.value for t in _i_dialogen(app.text_input) if t.label.startswith("Återkommande")] == ["varje lördag"]
    assert _spara_knapp(app)


def test_redigera_andrar_inget_innan_man_sparar(app, tmp_path):
    import lagring
    fore = lagring.JsonLager(tmp_path / "kort.json").alla()
    _oppna_redigera(app, "ex000001")
    assert lagring.JsonLager(tmp_path / "kort.json").alla() == fore
    assert [h.value for h in app.header] == ["Nya (1)", "Påbörjade (3)", "Avslutade (1)"]


def test_flytta_med_knapp_skriver_bara_status(app, tmp_path):
    import lagring
    fil = lagring.JsonLager(tmp_path / "kort.json")
    # Fjun ändrar ordning på kortet efter att appen läste det
    fil.andra_falt("ex000001", {"ordning": "5"})
    [b for b in app.button if b.key == "h_ex000001"][0].click().run()
    assert not app.exception
    kort = {x["id"]: x for x in fil.alla()}
    assert kort["ex000001"]["status"] == "påbörjad"
    assert kort["ex000001"]["ordning"] == "5"
    assert kort["ex000002"]["status"] == "påbörjad"  # övriga kort orörda
