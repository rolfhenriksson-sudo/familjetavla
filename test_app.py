"""Rökprov: appen startar i lokalt läge utan inloggning och klarar grundflödena."""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import kort as k


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("FAMILJETAVLA_LAGE", "lokal")
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
