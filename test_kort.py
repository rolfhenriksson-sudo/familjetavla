"""Tester för logiken i kort.py. Kör med: pytest -v"""
from datetime import date

import pytest

import kort as k


def test_nytt_kort_har_alla_falt_och_ar_ny():
    kort = k.nytt_kort("Handla", "Mjölk och bröd", "privat")
    assert list(kort.keys()) == k.FALT
    assert kort["status"] == "ny"
    assert kort["ansvarig"] == "Rolf"
    assert kort["skapad_av"] == "appen"
    assert len(kort["id"]) == 8


def test_tom_titel_ger_fel():
    with pytest.raises(ValueError):
        k.nytt_kort("   ", "", "privat")


def test_okand_typ_ger_fel():
    with pytest.raises(ValueError):
        k.nytt_kort("Något", "", "hemlig")


@pytest.mark.parametrize("typ", ["påminnelse", "återkommande"])
def test_paminnelse_och_aterkommande_hamnar_i_paborjad(typ):
    assert k.nytt_kort("X", "", typ)["status"] == "påbörjad"


@pytest.mark.parametrize("typ", ["privat", "jobb"])
def test_privat_och_jobb_hamnar_i_ny(typ):
    assert k.nytt_kort("X", "", typ)["status"] == "ny"


def test_varje_gang_blir_ett_nytt_kort():
    a = k.nytt_kort("Ring Peter", "", "återkommande", aterkommande="varje lördag")
    b = k.nytt_kort("Ring Peter", "", "återkommande", aterkommande="varje lördag")
    assert a["id"] != b["id"]


def test_aterkommande_text_sparas_bara_for_aterkommande():
    assert k.nytt_kort("X", "", "återkommande", aterkommande="varje dag")["återkommande"] == "varje dag"
    assert k.nytt_kort("X", "", "privat", aterkommande="varje dag")["återkommande"] == ""


def test_datum_ar_valfria_och_formateras():
    kort = k.nytt_kort("X", "", "jobb", startdatum=date(2026, 10, 5), slutdatum="2026-10-09")
    assert kort["startdatum"] == "2026-10-05"
    assert kort["slutdatum"] == "2026-10-09"
    tomt = k.nytt_kort("X", "", "jobb")
    assert tomt["startdatum"] == "" and tomt["slutdatum"] == ""


def test_slutdatum_fore_startdatum_ger_fel():
    with pytest.raises(ValueError):
        k.nytt_kort("X", "", "jobb", startdatum="2026-10-09", slutdatum="2026-10-01")


def test_ogiltigt_datum_ger_fel():
    with pytest.raises(ValueError):
        k.nytt_kort("X", "", "jobb", slutdatum="imorgon")


def test_tom_ansvarig_blir_standardanvandare():
    assert k.nytt_kort("X", "", "jobb", ansvarig="")["ansvarig"] == k.ANVANDARE[0]


def test_flytta_hoger_och_vanster():
    kort = k.nytt_kort("X", "", "privat")
    kort = k.flytta(kort, 1)
    assert kort["status"] == "påbörjad"
    kort = k.flytta(kort, -1)
    assert kort["status"] == "ny"


def test_flytta_stannar_vid_kanten():
    kort = k.nytt_kort("X", "", "privat")
    assert k.flytta(kort, -1)["status"] == "ny"
    for _ in range(5):
        kort = k.flytta(kort, 1)
    assert kort["status"] == "avslutad"
    assert not k.kan_flytta(kort, 1)
    assert k.kan_flytta(kort, -1)


def test_flytta_andrar_inte_originalet():
    kort = k.nytt_kort("X", "", "privat")
    k.flytta(kort, 1)
    assert kort["status"] == "ny"


def test_avslutad_datum_sätts_och_tomms():
    kort = k.nytt_kort("X", "", "privat")
    kort = k.flytta(kort, 2, idag=date(2026, 10, 23))
    assert kort["status"] == "avslutad"
    assert kort["avslutad_datum"] == "2026-10-23"
    kort = k.flytta(kort, -1)
    assert kort["avslutad_datum"] == ""


def test_avslutad_datum_skrivs_inte_over_nar_kortet_redan_ar_avslutat():
    kort = {**k.nytt_kort("X", "", "privat"), "status": "avslutad", "avslutad_datum": "2026-01-01"}
    assert k.flytta(kort, 1)["avslutad_datum"] == "2026-01-01"


def test_flytta_okand_status_ger_fel():
    kort = {**k.nytt_kort("X", "", "privat"), "status": "paus"}
    with pytest.raises(ValueError):
        k.flytta(kort, 1)
    assert not k.kan_flytta(kort, 1)


def test_farg_finns_for_alla_typer_och_fallback():
    for typ in k.TYPER:
        assert k.farg(typ)["bakgrund"].startswith("#")
    assert len({k.farg(t)["bakgrund"] for t in k.TYPER}) == len(k.TYPER)
    assert k.farg("okänd") == k.OKAND_FARG


def test_normalisera_fyller_i_och_rensar():
    kort = k.normalisera({"id": " a1 ", "titel": "Hej", "status": "", "extra": "x", "ordning": 3})
    assert list(kort.keys()) == k.FALT
    assert kort["id"] == "a1"
    assert kort["status"] == "ny"
    assert kort["ordning"] == "3"
    assert "extra" not in kort


def test_normalisera_bevarar_foralder_och_ordning():
    kort = k.normalisera({"id": "b", "titel": "Pass 2", "förälder_id": "a", "ordning": "2"})
    assert kort["förälder_id"] == "a"
    assert kort["ordning"] == "2"


def test_i_status_filtrerar_och_sorterar_efter_slutdatum():
    a = {**k.nytt_kort("B", "", "jobb", slutdatum="2026-11-01")}
    b = {**k.nytt_kort("A", "", "jobb", slutdatum="2026-10-01")}
    c = {**k.nytt_kort("C", "", "jobb")}  # inget slutdatum, sist
    d = {**k.nytt_kort("D", "", "påminnelse")}  # annan status
    assert [x["titel"] for x in k.i_status([a, b, c, d], "ny")] == ["A", "B", "C"]
    assert [x["titel"] for x in k.i_status([a, b, c, d], "påbörjad")] == ["D"]


def test_avslutade_id_och_hitta():
    a = k.nytt_kort("A", "", "privat")
    b = k.flytta(k.nytt_kort("B", "", "privat"), 2)
    assert k.avslutade_id([a, b]) == [b["id"]]
    assert k.hitta([a, b], a["id"]) is a
    assert k.hitta([a, b], "finns-inte") is None


# ------------------------------------------------------------- redigera

def _kort(**falt):
    return k.normalisera({"id": "a1", "titel": "Gammal", "typ": "privat", "status": "ny",
                          "ansvarig": "Rolf", **falt})


def test_redigera_utan_andring_ger_tom_dict():
    kort = _kort(beskrivning="B", startdatum="2026-10-01", slutdatum="2026-10-05")
    assert k.redigera(kort, "Gammal", "B", "privat", "Rolf", "2026-10-01", "2026-10-05") == {}


def test_redigera_returnerar_bara_andrade_falt():
    kort = _kort(beskrivning="B")
    assert k.redigera(kort, "Ny titel", "B", "privat", "Rolf") == {"titel": "Ny titel"}


def test_redigera_alla_falt_och_datum_som_date():
    kort = _kort()
    andringar = k.redigera(kort, " Ny ", " Text ", "jobb", "Fjun",
                           date(2026, 11, 1), date(2026, 11, 9))
    assert andringar == {"titel": "Ny", "beskrivning": "Text", "typ": "jobb",
                         "ansvarig": "Fjun", "startdatum": "2026-11-01",
                         "slutdatum": "2026-11-09"}


def test_redigera_ror_aldrig_skyddade_kolumner():
    kort = _kort(förälder_id="p1", ordning="3", skapad_av="fjun", avslutad_datum="2026-10-01",
                 status="avslutad")
    andringar = k.redigera(kort, "Ny", "", "privat", "Rolf")
    assert set(andringar) <= set(k.REDIGERBARA)
    for skyddad in ("id", "status", "förälder_id", "ordning", "skapad_av", "avslutad_datum"):
        assert skyddad not in andringar


def test_redigera_tom_titel_ger_fel():
    with pytest.raises(ValueError, match="Titel"):
        k.redigera(_kort(), "   ", "", "privat", "Rolf")


def test_redigera_okand_typ_ger_fel():
    with pytest.raises(ValueError, match="typ"):
        k.redigera(_kort(), "X", "", "hemlig", "Rolf")


def test_redigera_slut_fore_start_ger_fel():
    with pytest.raises(ValueError, match="Slutdatum"):
        k.redigera(_kort(), "X", "", "privat", "Rolf", "2026-10-10", "2026-10-09")


def test_redigera_samma_start_och_slut_ar_ok():
    assert k.redigera(_kort(), "Gammal", "", "privat", "Rolf", "2026-10-10", "2026-10-10") == {
        "startdatum": "2026-10-10", "slutdatum": "2026-10-10"}


def test_redigera_bara_slutdatum_eller_bara_startdatum_ar_ok():
    assert k.redigera(_kort(), "Gammal", "", "privat", "Rolf", "", "2026-10-10") == {
        "slutdatum": "2026-10-10"}
    assert k.redigera(_kort(), "Gammal", "", "privat", "Rolf", "2026-10-10", "") == {
        "startdatum": "2026-10-10"}


def test_redigera_ogiltigt_datum_ger_fel():
    with pytest.raises(ValueError, match="datum"):
        k.redigera(_kort(), "X", "", "privat", "Rolf", "i morgon", "")


def test_redigera_kan_tomma_datum():
    kort = _kort(startdatum="2026-10-01", slutdatum="2026-10-05")
    assert k.redigera(kort, "Gammal", "", "privat", "Rolf") == {"startdatum": "", "slutdatum": ""}


@pytest.mark.parametrize("ny_typ", ["påminnelse", "återkommande"])
def test_redigera_nytt_kort_som_blir_paminnelse_flyttas_till_paborjade(ny_typ):
    assert k.redigera(_kort(status="ny"), "Gammal", "", ny_typ, "Rolf")["status"] == "påbörjad"


@pytest.mark.parametrize("ny_typ", ["påminnelse", "återkommande"])
def test_redigera_avslutat_kort_flyttas_inte_vid_typbyte(ny_typ):
    kort = _kort(status="avslutad", avslutad_datum="2026-10-01")
    assert "status" not in k.redigera(kort, "Gammal", "", ny_typ, "Rolf")


def test_redigera_paborjat_kort_flyttas_inte_vid_typbyte():
    assert "status" not in k.redigera(_kort(status="påbörjad"), "Gammal", "", "påminnelse", "Rolf")


def test_redigera_ny_med_oforandrad_paminnelsetyp_flyttas_inte():
    # Handskrivet kort i 'ny' som redan är påminnelse: typen byts inte, så inget flyttas
    assert "status" not in k.redigera(_kort(typ="påminnelse", status="ny"), "Nytt", "", "påminnelse", "Rolf")


def test_redigera_aterkommande_text_sparas_bara_for_typen_aterkommande():
    kort = _kort(typ="återkommande", status="påbörjad", återkommande="varje lördag")
    assert k.redigera(kort, "Gammal", "", "återkommande", "Rolf", aterkommande="varje söndag") == {
        "återkommande": "varje söndag"}
    # Byter man bort från återkommande rörs texten inte
    assert "återkommande" not in k.redigera(kort, "Gammal", "", "privat", "Rolf", aterkommande="x")


def test_redigera_tom_ansvarig_blir_standard():
    assert k.redigera(_kort(ansvarig="Fjun"), "Gammal", "", "privat", "") == {"ansvarig": k.ANVANDARE[0]}


def test_redigera_kort_med_okand_typ_i_arket_kan_andras_utan_att_byta_typ():
    kort = _kort(typ="annat")
    assert k.redigera(kort, "Ny titel", "", "annat", "Rolf") == {"titel": "Ny titel"}
    with pytest.raises(ValueError, match="typ"):
        k.redigera(kort, "Ny titel", "", "hemlig", "Rolf")


# ------------------------------------------------------------- flytt_andringar

def test_flytt_andringar_ny_till_paborjad_andrar_bara_status():
    assert k.flytt_andringar(_kort(status="ny"), 1) == {"status": "påbörjad"}


def test_flytt_andringar_till_avslutad_satter_status_och_datum():
    assert k.flytt_andringar(_kort(status="påbörjad"), 1, idag="2026-10-23") == {
        "status": "avslutad", "avslutad_datum": "2026-10-23"}


def test_flytt_andringar_fran_avslutad_tommer_datum():
    kort = _kort(status="avslutad", avslutad_datum="2026-10-01")
    assert k.flytt_andringar(kort, -1) == {"status": "påbörjad", "avslutad_datum": ""}


def test_flytt_andringar_vid_kanten_ar_tom():
    assert k.flytt_andringar(_kort(status="ny"), -1) == {}
    assert k.flytt_andringar(_kort(status="avslutad", avslutad_datum="2026-10-01"), 1) == {}


def test_flytt_andringar_matchar_flytta():
    kort = _kort(status="påbörjad", ordning="2", förälder_id="p")
    assert {**kort, **k.flytt_andringar(kort, 1, idag="2026-10-23")} == k.flytta(kort, 1, idag="2026-10-23")
