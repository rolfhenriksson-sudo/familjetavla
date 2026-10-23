"""Tester för projekt och pass (version 2): logik, båda lagren och app-rökprov."""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import kort as k
import lagring
from test_lagring import LatsasFlik

IDAG = "2026-10-23"


def kort_(id_, titel="K", status="ny", typ="privat", **falt):
    return k.normalisera({"id": id_, "titel": titel, "typ": typ, "status": status,
                          "ansvarig": "Rolf", **falt})


def pass_(id_, foralder, ordning, status="ny", titel=None, **falt):
    return kort_(id_, titel or f"Pass {id_}", status, förälder_id=foralder,
                 ordning=str(ordning), **falt)


# ------------------------------------------------------------- logik: status och framsteg

@pytest.mark.parametrize("statusar, forvantat", [
    (["ny", "ny", "ny"], "ny"),
    (["påbörjad", "ny"], "påbörjad"),
    (["avslutad", "ny"], "påbörjad"),
    (["avslutad", "påbörjad"], "påbörjad"),
    (["avslutad", "avslutad"], "avslutad"),
    (["avslutad"], "avslutad"),
    (["konstigt", "ny"], "ny"),            # okänd status räknas som ny
    (["avslutad", "konstigt"], "påbörjad"),
])
def test_projektstatus(statusar, forvantat):
    passen = [pass_(f"p{i}", "pr", i, s) for i, s in enumerate(statusar, 1)]
    assert k.projektstatus(passen) == forvantat


def test_projektstatus_utan_pass_ar_inget_projekt():
    assert k.projektstatus([]) is None


@pytest.mark.parametrize("typ", ["påminnelse", "återkommande"])
def test_paminnelse_och_aterkommande_projekt_star_aldrig_i_ny(typ):
    passen = [pass_("a", "pr", 1), pass_("b", "pr", 2)]
    assert k.projektstatus(passen, typ) == "påbörjad"
    assert k.projektstatus([pass_("a", "pr", 1, "avslutad")], typ) == "avslutad"


def test_framsteg():
    passen = [pass_("a", "pr", 1, "avslutad"), pass_("b", "pr", 2, "påbörjad"), pass_("c", "pr", 3)]
    assert k.framsteg(passen) == (1, 3)
    assert k.framsteg_text(passen) == "1 av 3 pass klara"
    assert k.framsteg_text([]) == "0 av 0 pass klara"


def test_status_andringar_satter_och_tommer_avslutad_datum():
    kort = kort_("a", status="ny")
    assert k.status_andringar(kort, "avslutad", IDAG) == {"status": "avslutad", "avslutad_datum": IDAG}
    klar = kort_("a", status="avslutad", avslutad_datum="2026-10-01")
    assert k.status_andringar(klar, "avslutad", IDAG) == {}
    assert k.status_andringar(klar, "påbörjad") == {"status": "påbörjad", "avslutad_datum": ""}
    assert k.status_andringar(kort, "ny") == {}
    with pytest.raises(ValueError):
        k.status_andringar(kort, "nästan")


def test_projekt_andringar_skriver_bara_status_och_datum():
    pr = kort_("pr", status="ny", titel="Hallen")
    passen = [pass_("a", "pr", 1, "avslutad"), pass_("b", "pr", 2)]
    assert k.projekt_andringar(pr, passen, IDAG) == {"status": "påbörjad"}
    passen[1]["status"] = "avslutad"
    assert k.projekt_andringar(pr, passen, IDAG) == {"status": "avslutad", "avslutad_datum": IDAG}
    klar = kort_("pr", status="avslutad", avslutad_datum=IDAG)
    assert k.projekt_andringar(klar, passen, "2030-01-01") == {}  # redan rätt: inget skrivs
    passen[1]["status"] = "ny"
    assert k.projekt_andringar(klar, passen) == {"status": "påbörjad", "avslutad_datum": ""}
    assert k.projekt_andringar(pr, []) == {}  # inga pass: statusen styrs inte


# ------------------------------------------------------------- logik: vilka kort som visas

def test_pass_visas_inte_pa_tavlan_men_projektet_gor_det():
    lista = [kort_("pr"), pass_("a", "pr", 1), pass_("b", "pr", 2), kort_("vanligt")]
    assert [x["id"] for x in k.tavelkort(lista)] == ["pr", "vanligt"]
    assert k.ar_projekt(lista[0], lista) and not k.ar_projekt(lista[3], lista)
    assert not k.ar_foraldralost(lista[1], lista)


def test_passen_i_ordning_med_talsortering_och_trasig_ordning():
    lista = [kort_("pr"),
             pass_("tio", "pr", 10), pass_("tva", "pr", 2), pass_("ett", "pr", 1),
             pass_("tom", "pr", ""), pass_("text", "pr", "snart"),
             pass_("tva_b", "pr", 2)]
    ids = [p["id"] for p in k.passen_till(lista, "pr")]
    # tal i storleksordning, lika ordning behåller arkets ordning, utan tal sist
    assert ids == ["ett", "tva", "tva_b", "tio", "tom", "text"]


def test_foraldralosa_pass_visas_som_vanliga_kort():
    lista = [
        kort_("pr"), pass_("ok", "pr", 1),
        pass_("vilse", "finns-inte", 1),          # föräldern saknas
        pass_("sjalv", "sjalv", 1),               # pekar på sig själv
        pass_("barnbarn", "ok", 1),               # föräldern är själv ett pass
        pass_("x", "y", 1), pass_("y", "x", 1),   # cirkel
    ]
    synliga = [x["id"] for x in k.tavelkort(lista)]
    assert synliga == ["pr", "vilse", "sjalv", "barnbarn", "x", "y"]
    assert all(k.ar_foraldralost(x, lista) for x in lista if x["id"] in synliga[1:])
    assert k.passen_till(lista, "ok") == []   # ett pass kan inte ha egna pass
    assert [p["id"] for p in k.passen_till(lista, "pr")] == ["ok"]


def test_avslutade_id_tar_projekt_med_pass_men_inte_klara_pass_i_pagaende_projekt():
    lista = [
        kort_("klart", status="avslutad"),
        kort_("proj_klart", status="avslutad"),
        pass_("k1", "proj_klart", 1, "avslutad"), pass_("k2", "proj_klart", 2, "avslutad"),
        kort_("proj_pagar", status="påbörjad"),
        pass_("p1", "proj_pagar", 1, "avslutad"), pass_("p2", "proj_pagar", 2),
        pass_("vilse", "saknas", 1, "avslutad"),
    ]
    assert sorted(k.avslutade_id(lista)) == sorted(["klart", "proj_klart", "k1", "k2", "vilse"])


# ------------------------------------------------------------- logik: nytt pass och ordning

def test_nytt_pass_arver_typ_och_ansvarig():
    pr = kort_("pr", typ="jobb", ansvarig="Rolf", status="påbörjad")
    p = k.nytt_pass(pr, " Spackla ", startdatum="2026-10-24", ordning=3)
    assert list(p.keys()) == k.FALT
    assert (p["typ"], p["förälder_id"], p["ordning"], p["status"], p["titel"]) == \
           ("jobb", "pr", "3", "ny", "Spackla")
    assert p["id"] != "pr"
    with pytest.raises(ValueError):
        k.nytt_pass(pr, "  ")
    with pytest.raises(ValueError, match="Slutdatum"):
        k.nytt_pass(pr, "X", startdatum="2026-10-10", slutdatum="2026-10-01")


def test_pass_efter_infogning_sist_utan_andra_skrivningar():
    passen = [pass_("a", "pr", 1), pass_("b", "pr", 2)]
    assert k.pass_efter_infogning(passen) == (3, {})
    assert k.pass_efter_infogning([]) == (1, {})
    assert k.pass_efter_infogning(passen, "finns-inte") == (3, {})


def test_pass_efter_infogning_fore_ett_pass_skjuter_de_efter():
    passen = [pass_("a", "pr", 1), pass_("b", "pr", 2), pass_("c", "pr", 3)]
    assert k.pass_efter_infogning(passen, "b") == (2, {"b": {"ordning": "3"}, "c": {"ordning": "4"}})
    assert k.pass_efter_infogning(passen, "a") == (
        1, {"a": {"ordning": "2"}, "b": {"ordning": "3"}, "c": {"ordning": "4"}})


def test_pass_efter_infogning_sist_lagar_trasig_ordning():
    passen = [pass_("a", "pr", 1), pass_("b", "pr", 5), pass_("c", "pr", "")]
    ordning, andringar = k.pass_efter_infogning(passen)
    assert ordning == 4
    assert andringar == {"b": {"ordning": "2"}, "c": {"ordning": "3"}}  # a rörs inte


def test_flytta_pass_byter_plats_och_skriver_bara_de_som_andras():
    passen = [pass_("a", "pr", 1), pass_("b", "pr", 2), pass_("c", "pr", 3)]
    assert k.flytta_pass(passen, "b", -1) == {"a": {"ordning": "2"}, "b": {"ordning": "1"}}
    assert k.flytta_pass(passen, "b", 1) == {"b": {"ordning": "3"}, "c": {"ordning": "2"}}
    assert k.flytta_pass(passen, "a", -1) == {}   # redan överst
    assert k.flytta_pass(passen, "c", 1) == {}    # redan nederst
    assert k.flytta_pass(passen, "okänt", 1) == {}


def test_flytta_pass_med_trasig_ordning_numrerar_om():
    passen = [pass_("a", "pr", 1), pass_("b", "pr", 1), pass_("c", "pr", "")]
    # a och b har samma ordning, c saknar. Efter flytten är allt 1, 2, 3.
    assert k.flytta_pass(passen, "c", -1) == {"b": {"ordning": "3"}, "c": {"ordning": "2"}}


# ------------------------------------------------------------- båda lagren

def _lager_json(tmp_path):
    return lagring.JsonLager(tmp_path / "k.json", med_exempel=False)


def _lager_sheets(tmp_path):
    return lagring.SheetsLager(LatsasFlik(k.FALT))


@pytest.fixture(params=[_lager_json, _lager_sheets], ids=["json", "sheets"])
def lager(request, tmp_path):
    return request.param(tmp_path)


def _per_id(lager):
    return {x["id"]: x for x in lager.alla()}


def _projekt(lager, titlar=("Skrapa", "Spackla", "Måla"), **falt):
    pr, passen = lagring.skapa_projekt(
        lager, "Hallväggen", "Måla hallen", falt.pop("typ", "privat"), "Rolf",
        pass_titlar=list(titlar), idag=IDAG, **falt)
    return pr, passen


def test_skapa_projekt_med_pass(lager):
    pr, passen = _projekt(lager, typ="jobb", startdatum="2026-10-24")
    sparat = _per_id(lager)
    assert len(sparat) == 4
    assert sparat[pr["id"]]["status"] == "ny" and sparat[pr["id"]]["förälder_id"] == ""
    assert [(p["titel"], p["ordning"], p["förälder_id"], p["typ"], p["status"]) for p in passen] == [
        ("Skrapa", "1", pr["id"], "jobb", "ny"),
        ("Spackla", "2", pr["id"], "jobb", "ny"),
        ("Måla", "3", pr["id"], "jobb", "ny")]
    assert [p["titel"] for p in k.passen_till(lager.alla(), pr["id"])] == ["Skrapa", "Spackla", "Måla"]
    assert [x["id"] for x in k.tavelkort(lager.alla())] == [pr["id"]]


def test_skapa_projekt_utan_pass_ar_ett_vanligt_kort_och_tomma_rader_hoppas_over(lager):
    pr, passen = lagring.skapa_projekt(lager, "Bara kort", pass_titlar=["", "  "])
    assert passen == [] and len(lager.alla()) == 1
    pr2, passen2 = lagring.skapa_projekt(lager, "Med pass", pass_titlar=["", "Ett", " ", "Två"])
    assert [p["titel"] for p in passen2] == ["Ett", "Två"]
    assert [p["ordning"] for p in passen2] == ["1", "2"]


def test_skapa_projekt_ogiltigt_skriver_ingenting(lager):
    with pytest.raises(ValueError):
        lagring.skapa_projekt(lager, " ", pass_titlar=["A"])
    with pytest.raises(ValueError, match="Slutdatum"):
        lagring.skapa_projekt(lager, "X", startdatum="2026-10-10", slutdatum="2026-10-01", pass_titlar=["A"])
    assert lager.alla() == []


def test_projektets_status_foljer_passen_och_skrivs(lager):
    pr, (a, b, c) = _projekt(lager)
    lagring.satt_pass_status(lager, a["id"], "påbörjad", IDAG)
    assert _per_id(lager)[pr["id"]]["status"] == "påbörjad"
    for p in (a, b):
        lagring.satt_pass_status(lager, p["id"], "avslutad", IDAG)
    sparat = _per_id(lager)
    assert sparat[pr["id"]]["status"] == "påbörjad" and sparat[a["id"]]["avslutad_datum"] == IDAG
    lagring.satt_pass_status(lager, c["id"], "avslutad", IDAG)
    sparat = _per_id(lager)
    assert (sparat[pr["id"]]["status"], sparat[pr["id"]]["avslutad_datum"]) == ("avslutad", IDAG)
    # ångra ett pass: projektet öppnas igen och datumet töms
    lagring.satt_pass_status(lager, c["id"], "ny")
    sparat = _per_id(lager)
    assert (sparat[pr["id"]]["status"], sparat[pr["id"]]["avslutad_datum"]) == ("påbörjad", "")
    assert sparat[c["id"]]["avslutad_datum"] == ""
    lagring.satt_pass_status(lager, a["id"], "ny")
    lagring.satt_pass_status(lager, b["id"], "ny")
    assert _per_id(lager)[pr["id"]]["status"] == "ny"


def test_satt_pass_status_bevarar_det_fjun_skrivit_pa_passet(lager):
    pr, (a, b, c) = _projekt(lager)
    lager.andra_falt(a["id"], {"beskrivning": "Fjuns text", "ansvarig": "Annan"})
    lagring.satt_pass_status(lager, a["id"], "avslutad", IDAG)
    sparat = _per_id(lager)[a["id"]]
    assert sparat["beskrivning"] == "Fjuns text" and sparat["ansvarig"] == "Annan"
    assert sparat["ordning"] == "1" and sparat["förälder_id"] == pr["id"]


def test_projektstatus_ror_inte_andra_falt_pa_projektet(lager):
    pr, (a, *_) = _projekt(lager)
    lager.andra_falt(pr["id"], {"beskrivning": "Fjun ändrade", "slutdatum": "2026-12-01"})
    lagring.satt_pass_status(lager, a["id"], "påbörjad")
    sparat = _per_id(lager)[pr["id"]]
    assert (sparat["beskrivning"], sparat["slutdatum"], sparat["status"]) == \
           ("Fjun ändrade", "2026-12-01", "påbörjad")


def test_lagg_till_pass_sist_och_fore(lager):
    pr, (a, b, c) = _projekt(lager)
    d = lagring.lagg_till_pass(lager, pr["id"], "Städa", slutdatum="2026-11-01")
    assert d["ordning"] == "4" and d["typ"] == "privat" and d["förälder_id"] == pr["id"]
    e = lagring.lagg_till_pass(lager, pr["id"], "Förbereda", fore_id=b["id"])
    assert e["ordning"] == "2"
    titlar = [p["titel"] for p in k.passen_till(lager.alla(), pr["id"])]
    assert titlar == ["Skrapa", "Förbereda", "Spackla", "Måla", "Städa"]
    assert [p["ordning"] for p in k.passen_till(lager.alla(), pr["id"])] == ["1", "2", "3", "4", "5"]


def test_nytt_pass_i_klart_projekt_oppnar_det_igen(lager):
    pr, (a,) = _projekt(lager, titlar=["Enda"])
    lagring.satt_pass_status(lager, a["id"], "avslutad", IDAG)
    assert _per_id(lager)[pr["id"]]["status"] == "avslutad"
    lagring.lagg_till_pass(lager, pr["id"], "Mer arbete")
    sparat = _per_id(lager)[pr["id"]]
    assert (sparat["status"], sparat["avslutad_datum"]) == ("påbörjad", "")


def test_vanligt_kort_blir_projekt_av_sitt_forsta_pass(lager):
    vanligt = k.nytt_kort("Städa garaget", "", "jobb")
    lager.lagg_till(vanligt)
    lagring.lagg_till_pass(lager, vanligt["id"], "Sortera")
    sparat = _per_id(lager)
    assert k.ar_projekt(sparat[vanligt["id"]], lager.alla())
    assert sparat[vanligt["id"]]["status"] == "ny"
    assert [p["typ"] for p in k.passen_till(lager.alla(), vanligt["id"])] == ["jobb"]


def test_avslutat_vanligt_kort_som_far_pass_foljer_passen(lager):
    kort = {**k.nytt_kort("Klart kort"), "status": "avslutad", "avslutad_datum": "2026-10-01"}
    lager.lagg_till(kort)
    lagring.lagg_till_pass(lager, kort["id"], "Nytt jobb")
    sparat = _per_id(lager)[kort["id"]]
    assert (sparat["status"], sparat["avslutad_datum"]) == ("ny", "")


def test_lagg_till_pass_fel_skriver_ingenting(lager):
    pr, (a, b) = _projekt(lager, titlar=["A", "B"])
    fore = lager.alla()
    with pytest.raises(ValueError):
        lagring.lagg_till_pass(lager, pr["id"], "  ", fore_id=a["id"])
    with pytest.raises(ValueError, match="själv ha pass"):
        lagring.lagg_till_pass(lager, a["id"], "Barnbarn")
    with pytest.raises(lagring.LagerFel):
        lagring.lagg_till_pass(lager, "finns-inte", "X")
    assert lager.alla() == fore


def test_flytta_pass_upp_och_ner_skriver_bara_ordning(lager):
    pr, (a, b, c) = _projekt(lager)
    lagring.flytta_pass(lager, c["id"], -1)
    assert [p["titel"] for p in k.passen_till(lager.alla(), pr["id"])] == ["Skrapa", "Måla", "Spackla"]
    lagring.flytta_pass(lager, a["id"], 1)
    assert [p["titel"] for p in k.passen_till(lager.alla(), pr["id"])] == ["Måla", "Skrapa", "Spackla"]
    assert lagring.flytta_pass(lager, b["id"], 1) == {}  # Spackla står redan sist
    assert _per_id(lager)[pr["id"]]["status"] == "ny"   # projektet rördes inte


def test_redigera_pass_andrar_bara_titel_och_datum(lager):
    pr, (a, b) = _projekt(lager, titlar=["A", "B"], typ="jobb")
    andringar = lagring.redigera_pass(lager, b["id"], "B2", "text", "2026-10-01", "2026-10-02")
    assert set(andringar) == {"titel", "beskrivning", "startdatum", "slutdatum"}
    sparat = _per_id(lager)
    assert sparat[b["id"]] == {**b, "titel": "B2", "beskrivning": "text",
                               "startdatum": "2026-10-01", "slutdatum": "2026-10-02"}
    assert sparat[a["id"]] == a
    with pytest.raises(ValueError, match="Slutdatum"):
        lagring.redigera_pass(lager, b["id"], "B3", "", "2026-10-05", "2026-10-01")
    with pytest.raises(ValueError):
        lagring.redigera_pass(lager, b["id"], " ")
    assert _per_id(lager)[b["id"]]["titel"] == "B2"


def test_ta_bort_pass_raknar_om_projektets_status(lager):
    pr, (a, b, c) = _projekt(lager)
    lagring.satt_pass_status(lager, a["id"], "avslutad", IDAG)
    lagring.satt_pass_status(lager, b["id"], "avslutad", IDAG)
    lagring.ta_bort_pass(lager, c["id"])   # kvar: två avslutade pass
    sparat = _per_id(lager)
    assert c["id"] not in sparat
    assert sparat[pr["id"]]["status"] == "avslutad"
    assert [p["ordning"] for p in k.passen_till(lager.alla(), pr["id"])] == ["1", "2"]


def test_ta_bort_sista_passet_gor_projektet_till_vanligt_kort(lager):
    pr, (a,) = _projekt(lager, titlar=["Enda"])
    lagring.satt_pass_status(lager, a["id"], "påbörjad")
    lagring.ta_bort_pass(lager, a["id"])
    sparat = _per_id(lager)
    assert list(sparat) == [pr["id"]]
    assert not k.ar_projekt(sparat[pr["id"]], lager.alla())
    assert sparat[pr["id"]]["status"] == "påbörjad"   # kortet står kvar där det var


def test_ta_bort_projekt_tar_med_passen_men_inget_annat(lager):
    pr, passen = _projekt(lager)
    pr2, passen2 = _projekt(lager, titlar=["Annat"])
    vanligt = k.nytt_kort("Vanligt")
    lager.lagg_till(vanligt)
    assert lagring.ta_bort_projekt(lager, pr["id"]) == 4
    kvar = _per_id(lager)
    assert set(kvar) == {pr2["id"], passen2[0]["id"], vanligt["id"]}
    with pytest.raises(lagring.LagerFel):
        lagring.ta_bort_projekt(lager, pr["id"])


def test_ta_bort_projekt_tar_med_pass_som_fjun_lagt_till_efter_att_appen_last(lager):
    pr, passen = _projekt(lager, titlar=["A"])
    lager.lagg_till(pass_("fjunpass", pr["id"], 2, titel="Fjuns pass"))
    lagring.ta_bort_projekt(lager, pr["id"])
    assert lager.alla() == []


def test_rensa_avslutade_tar_klara_projekt_men_inte_klara_pass_i_pagaende(lager):
    klart, (k1, k2) = _projekt(lager, titlar=["A", "B"])
    pagar, (p1, p2) = _projekt(lager, titlar=["C", "D"])
    for p in (k1, k2, p1):
        lagring.satt_pass_status(lager, p["id"], "avslutad", IDAG)
    vanligt = {**k.nytt_kort("Klart vanligt"), "status": "avslutad"}
    lager.lagg_till(vanligt)
    lager.ta_bort_flera(k.avslutade_id(lager.alla()))
    assert set(_per_id(lager)) == {pagar["id"], p1["id"], p2["id"]}


def test_redigera_projekt_ger_passen_ny_typ_och_synkar(lager):
    pr, (a, b) = _projekt(lager, titlar=["A", "B"])
    lagring.satt_pass_status(lager, a["id"], "avslutad", IDAG)
    lagring.redigera_projekt(lager, _per_id(lager)[pr["id"]], "Ny titel", "", "jobb", "Rolf")
    sparat = _per_id(lager)
    assert sparat[pr["id"]]["titel"] == "Ny titel" and sparat[pr["id"]]["status"] == "påbörjad"
    assert {sparat[a["id"]]["typ"], sparat[b["id"]]["typ"]} == {"jobb"}
    # titeln på pass rördes inte
    assert sparat[a["id"]]["titel"] == "A"


def test_nytt_projekt_av_typ_paminnelse_hamnar_i_paborjad(lager):
    pr, _ = _projekt(lager, typ="påminnelse")
    assert _per_id(lager)[pr["id"]]["status"] == "påbörjad"


def test_synka_alla_skriver_projekt_vars_pass_fjun_andrat(lager):
    pr, (a, b) = _projekt(lager, titlar=["A", "B"])
    lager.andra_falt(a["id"], {"status": "avslutad"})   # Fjun, direkt i arket
    lager.andra_falt(b["id"], {"status": "avslutad"})
    lista, fel = lagring.synka_alla(lager, lager.alla(), IDAG)
    assert fel == []
    assert [x for x in lista if x["id"] == pr["id"]][0]["status"] == "avslutad"
    sparat = _per_id(lager)[pr["id"]]
    assert (sparat["status"], sparat["avslutad_datum"]) == ("avslutad", IDAG)
    # redan synkat: andra körningen skriver inget
    assert lagring.synka_alla(lager, lager.alla(), IDAG)[1] == []


def test_synka_alla_visar_ratt_status_aven_om_skrivningen_misslyckas(lager, monkeypatch):
    pr, (a,) = _projekt(lager, titlar=["A"])
    lager.andra_falt(a["id"], {"status": "påbörjad"})
    lista = lager.alla()

    def fel_vid_skrivning(*_a, **_k):
        raise RuntimeError("nätverksfel")
    monkeypatch.setattr(lager, "andra_falt", fel_vid_skrivning)
    ny, fel = lagring.synka_alla(lager, lista)
    assert [x for x in ny if x["id"] == pr["id"]][0]["status"] == "påbörjad"
    assert len(fel) == 1 and "nätverksfel" in fel[0]


def test_trasig_data_kraschar_inte(lager):
    pr, (a, b) = _projekt(lager, titlar=["A", "B"])
    lager.lagg_till(pass_("vilse", "finns-inte", 1))
    lager.lagg_till(pass_("cirkel", "cirkel", ""))
    lager.andra_falt(a["id"], {"ordning": "x", "status": "konstigt"})
    lista, fel = lagring.synka_alla(lager, lager.alla(), IDAG)
    assert fel == []
    assert {x["id"] for x in k.tavelkort(lista)} == {pr["id"], "vilse", "cirkel"}
    lagring.satt_pass_status(lager, "vilse", "avslutad", IDAG)   # föräldralöst pass: ingen krasch
    lagring.ta_bort_pass(lager, "vilse")


# ------------------------------------------------------------- Sheets: rätt rad och inga onödiga skrivningar

def _sheets():
    flik = LatsasFlik(k.FALT)
    return lagring.SheetsLager(flik), flik


def test_sheets_pass_sist_skriver_bara_en_ny_rad_och_projektets_status():
    lager, flik = _sheets()
    pr, passen = lagring.skapa_projekt(lager, "P", pass_titlar=["A", "B"])
    flik.anrop.clear()
    lagring.lagg_till_pass(lager, pr["id"], "C")
    assert flik.anrop == [("append", "RAW")]   # ny rad sist, ingenting annat skrevs om


def test_sheets_status_pa_pass_skriver_passets_rad_och_projektets_rad_bara():
    lager, flik = _sheets()
    vanligt = k.nytt_kort("Vanligt")
    lager.lagg_till(vanligt)
    pr, (a, b) = lagring.skapa_projekt(lager, "P", pass_titlar=["A", "B"])
    rader_fore = [list(r) for r in flik.rader]
    flik.anrop.clear()
    lagring.satt_pass_status(lager, a["id"], "påbörjad")
    skrivna = {a_[1].split(":")[0][1:] for a_ in flik.anrop}
    nr = {r[0]: i + 1 for i, r in enumerate(flik.rader)}
    assert skrivna == {str(nr[a["id"]]), str(nr[pr["id"]])}
    # övriga rader (vanligt kort, pass B) är orörda
    assert flik.rader[nr[vanligt["id"]] - 1] == rader_fore[nr[vanligt["id"]] - 1]
    assert flik.rader[nr[b["id"]] - 1] == rader_fore[nr[b["id"]] - 1]


def test_sheets_flytta_pass_skriver_bara_de_tva_passens_rader():
    lager, flik = _sheets()
    pr, (a, b, c) = lagring.skapa_projekt(lager, "P", pass_titlar=["A", "B", "C"])
    flik.anrop.clear()
    lagring.flytta_pass(lager, b["id"], 1)
    nr = {r[0]: i + 1 for i, r in enumerate(flik.rader)}
    assert sorted(a_[1] for a_ in flik.anrop) == sorted([f"A{nr[b['id']]}:M{nr[b['id']]}",
                                                         f"A{nr[c['id']]}:M{nr[c['id']]}"])


def test_sheets_ta_bort_projekt_raderar_ratt_rader_nar_flera_projekt_ar_blandade():
    lager, flik = _sheets()
    p1, (a1, a2) = lagring.skapa_projekt(lager, "Ett", pass_titlar=["A", "B"])
    p2, (b1,) = lagring.skapa_projekt(lager, "Två", pass_titlar=["C"])
    lager.lagg_till(pass_("a3", p1["id"], 3))   # ett pass längre ned i arket
    lagring.ta_bort_projekt(lager, p1["id"])
    kvar = [r[0] for r in flik.rader[1:]]
    assert sorted(kvar) == sorted([p2["id"], b1["id"]])
    assert [a_[1] for a_ in flik.anrop if a_[0] == "delete"] == sorted(
        [a_[1] for a_ in flik.anrop if a_[0] == "delete"], reverse=True)


def test_sheets_fjun_skriver_pass_med_forald_id_och_ordning_som_text():
    flik = LatsasFlik(k.FALT, [
        ["hall0001", "Hallväggen", "", "privat", "ny", "Rolf", "", "", "", "", "", "fjun", ""],
        ["hall0002", "Skrapa", "", "privat", "avslutad", "Rolf", "", "", "hall0001", "1", "", "fjun", "2026-10-20"],
        ["hall0003", "Måla", "", "privat", "ny", "Rolf", "", "", "hall0001", "2", "", "fjun", ""],
    ])
    lager = lagring.SheetsLager(flik)
    pass_fore = [list(r) for r in flik.rader[2:]]
    lista, fel = lagring.synka_alla(lager, lager.alla(), IDAG)
    assert fel == []
    assert [x["id"] for x in k.tavelkort(lista)] == ["hall0001"]
    assert k.framsteg_text(k.passen_till(lista, "hall0001")) == "1 av 2 pass klara"
    assert flik.rader[1][4] == "påbörjad"          # projektraden fick sin status
    assert flik.rader[1][1] == "Hallväggen" and flik.rader[1][11] == "fjun"
    assert flik.rader[2:] == pass_fore              # passens rader är orörda
    assert [a_[1] for a_ in flik.anrop] == ["A2:M2"]


# ------------------------------------------------------------- app-rökprov (lokalt läge)

@pytest.fixture
def tavla(tmp_path, monkeypatch):
    """Appen med exempelkorten plus projektet 'Hallväggen' med tre pass (utan att röra riktiga arket)."""
    monkeypatch.setenv("FAMILJETAVLA_LAGE", "lokal")
    monkeypatch.delenv("APP_LOSENORD", raising=False)  # testerna ska inte påverkas av ens egen miljö
    monkeypatch.setenv("FAMILJETAVLA_FIL", str(tmp_path / "kort.json"))
    st.cache_resource.clear()
    lager = lagring.JsonLager(tmp_path / "kort.json")
    pr, passen = lagring.skapa_projekt(lager, "Hallväggen", "Måla om", "privat", "Rolf",
                                       pass_titlar=["Skrapa", "Spackla", "Måla"])
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception
    at.lager, at.projekt, at.passen = lager, pr, passen
    return at


def _knapp(at, nyckel):
    return [b for b in at.button if b.key == nyckel][0]


def _rubriker(at):
    return [h.value for h in at.header]


def _kortrutor(at):
    """Nycklarna för korten på tavlan (pass har egna nycklar och räknas inte)."""
    return [b.key for b in at.button if b.key and b.key.startswith("e_")]


def test_projektet_visas_som_ett_kort_med_framsteg_och_passen_ar_inga_egna_kort(tavla):
    assert _rubriker(tavla) == ["Nya (2)", "Påbörjade (3)", "Avslutade (1)"]  # exempelkorten + projektet
    assert f"e_{tavla.projekt['id']}" in _kortrutor(tavla)
    assert all(f"e_{p['id']}" not in _kortrutor(tavla) for p in tavla.passen)
    html = " ".join(m.value for m in tavla.markdown)
    assert "0 av 3 pass klara" in html and "Hallväggen" in html
    assert "Skrapa" in html   # passen visas i projektkortets lista


def test_projektkortet_har_inga_aktiva_flyttknappar(tavla):
    pid = tavla.projekt["id"]
    assert _knapp(tavla, f"v_{pid}").disabled and _knapp(tavla, f"h_{pid}").disabled


def test_bocka_av_pass_uppdaterar_framsteg_och_projektets_status(tavla):
    pid, (a, b, c) = tavla.projekt["id"], tavla.passen
    _knapp(tavla, f"pk_{a['id']}").click().run()
    assert not tavla.exception
    assert "1 av 3 pass klara" in " ".join(m.value for m in tavla.markdown)
    assert _rubriker(tavla) == ["Nya (1)", "Påbörjade (4)", "Avslutade (1)"]
    assert {x["id"]: x for x in tavla.lager.alla()}[pid]["status"] == "påbörjad"   # skrevs till lagret
    _knapp(tavla, f"pk_{b['id']}").click().run()
    _knapp(tavla, f"pk_{c['id']}").click().run()
    assert _rubriker(tavla) == ["Nya (1)", "Påbörjade (3)", "Avslutade (2)"]
    sparat = {x["id"]: x for x in tavla.lager.alla()}[pid]
    assert sparat["status"] == "avslutad" and sparat["avslutad_datum"]
    _knapp(tavla, f"pk_{c['id']}").click().run()   # ångra
    assert {x["id"]: x for x in tavla.lager.alla()}[pid]["status"] == "påbörjad"


def test_paborja_pass_flyttar_projektet_till_paborjade(tavla):
    a = tavla.passen[0]
    _knapp(tavla, f"pp_{a['id']}").click().run()
    assert _rubriker(tavla)[1] == "Påbörjade (4)"
    assert {x["id"]: x for x in tavla.lager.alla()}[a["id"]]["status"] == "påbörjad"


def test_flytta_pass_upp_och_ner(tavla):
    a, b, c = tavla.passen
    assert _knapp(tavla, f"pu_{a['id']}").disabled and _knapp(tavla, f"pn_{c['id']}").disabled
    _knapp(tavla, f"pn_{a['id']}").click().run()
    assert [p["titel"] for p in k.passen_till(tavla.lager.alla(), tavla.projekt["id"])] == \
           ["Spackla", "Skrapa", "Måla"]


def _i_form(widgets, form_id):
    return [w for w in widgets if (w.form_id or "") == form_id]


def test_lagg_till_pass_med_formularet(tavla):
    pid = tavla.projekt["id"]
    form = f"nytt_pass_{pid}"
    _i_form(tavla.text_input, form)[0].set_value("Städa efter")
    [b for b in _i_form(tavla.button, form)][0].click().run()
    assert not tavla.exception
    titlar = [p["titel"] for p in k.passen_till(tavla.lager.alla(), pid)]
    assert titlar == ["Skrapa", "Spackla", "Måla", "Städa efter"]
    assert "0 av 4 pass klara" in " ".join(m.value for m in tavla.markdown)


def test_lagg_till_pass_utan_titel_ger_varning(tavla):
    form = f"nytt_pass_{tavla.projekt['id']}"
    _i_form(tavla.button, form)[0].click().run()
    assert any("Titel" in w.value for w in tavla.warning)
    assert len(tavla.lager.alla()) == 5 + 4


def test_ta_bort_pass(tavla):
    b = tavla.passen[1]
    _knapp(tavla, f"pr_{b['id']}").click().run()
    assert [p["titel"] for p in k.passen_till(tavla.lager.alla(), tavla.projekt["id"])] == ["Skrapa", "Måla"]
    assert "0 av 2 pass klara" in " ".join(m.value for m in tavla.markdown)


def test_ta_bort_projekt_kraver_bekraftelse_och_tar_med_passen(tavla):
    pid = tavla.projekt["id"]
    _knapp(tavla, f"r_{pid}").click().run()
    assert len(tavla.lager.alla()) == 9                       # inget borttaget än
    assert any("alla 3 pass" in w.value for w in tavla.warning)
    _knapp(tavla, f"rnej_{pid}").click().run()
    assert len(tavla.lager.alla()) == 9
    _knapp(tavla, f"r_{pid}").click().run()
    _knapp(tavla, f"rja_{pid}").click().run()
    assert not tavla.exception
    assert len(tavla.lager.alla()) == 5                       # bara exempelkorten kvar
    assert _rubriker(tavla) == ["Nya (1)", "Påbörjade (3)", "Avslutade (1)"]


def test_rensa_avslutade_tar_avslutat_projekt_med_pass_men_inte_pagaende(tavla):
    lager = tavla.lager
    klart, (k1,) = lagring.skapa_projekt(lager, "Klart projekt", pass_titlar=["Enda"])
    lagring.satt_pass_status(lager, k1["id"], "avslutad")
    a = tavla.passen[0]
    lagring.satt_pass_status(lager, a["id"], "avslutad")      # pågående projekt med ett klart pass
    tavla.run()
    assert _rubriker(tavla)[2] == "Avslutade (2)"             # exempelkortet + klart projekt
    _knapp(tavla, "rensa").click().run()
    assert any("deras 1 pass" in w.value for w in tavla.warning)
    _knapp(tavla, "rensa_ja").click().run()
    kvar = {x["id"] for x in lager.alla()}
    assert klart["id"] not in kvar and k1["id"] not in kvar and "ex000005" not in kvar
    assert tavla.projekt["id"] in kvar and a["id"] in kvar    # pågående projektet orört


def test_skapa_projekt_i_formularet_med_pass(tavla):
    tavla.text_input[0].set_value("Bygga altan")
    tavla.text_area[1].set_value("Gräva\nGjuta\n\nBygga")
    tavla.button[0].click().run()
    assert not tavla.exception
    lista = tavla.lager.alla()
    pr = [x for x in lista if x["titel"] == "Bygga altan"][0]
    assert [p["titel"] for p in k.passen_till(lista, pr["id"])] == ["Gräva", "Gjuta", "Bygga"]
    assert "0 av 3 pass klara" in " ".join(m.value for m in tavla.markdown)


def test_skapa_vanligt_kort_i_formularet_fungerar_som_forut(tavla):
    tavla.text_input[0].set_value("Bara ett kort")
    tavla.button[0].click().run()
    kort = [x for x in tavla.lager.alla() if x["titel"] == "Bara ett kort"][0]
    assert k.passen_till(tavla.lager.alla(), kort["id"]) == []


def test_projekt_av_paminnelse_visas_i_paborjade(tavla):
    tavla.selectbox[0].select("påminnelse")
    tavla.text_input[0].set_value("Årliga kontroller")
    tavla.text_area[1].set_value("Brandvarnare\nSläckare")
    tavla.button[0].click().run()
    assert _rubriker(tavla)[1] == "Påbörjade (4)"   # tre exempelkort + det nya projektet


def test_foraldralost_pass_visas_som_vanligt_kort_utan_krasch(tavla):
    tavla.lager.lagg_till(pass_("vilse01", "finns-inte", 1, titel="Vilsekommet pass"))
    tavla.run()
    assert not tavla.exception
    assert "e_vilse01" in _kortrutor(tavla)
    assert _knapp(tavla, "h_vilse01").disabled is False       # beter sig som ett vanligt kort
    assert any("saknar projekt" in c.value for c in tavla.caption)


def test_pass_med_trasig_data_kraschar_inte(tavla):
    lager, a = tavla.lager, tavla.passen[0]
    lager.andra_falt(a["id"], {"status": "???", "ordning": "x", "startdatum": "inte-ett-datum"})
    lager.lagg_till(pass_("cirkel1", "cirkel2", 1))
    lager.lagg_till(pass_("cirkel2", "cirkel1", 1))
    tavla.run()
    assert not tavla.exception


def test_redigera_dialogen_for_projekt_visar_forklaring_och_for_vanligt_kort_forsta_pass(tavla):
    [b for b in tavla.button if b.key == f"e_{tavla.projekt['id']}"][0].click().run()
    assert not tavla.exception
    assert not any(t.label == "Första pass (valfritt)" for t in tavla.text_input)
    assert any("följer passen" in c.value for c in tavla.caption)
    tavla.run()
    [b for b in tavla.button if b.key == "e_ex000001"][0].click().run()
    assert any(t.label == "Första pass (valfritt)" for t in tavla.text_input)
