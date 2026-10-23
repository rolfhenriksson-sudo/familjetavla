"""Familjetavlan – webbgränssnittet.

Starta med:  streamlit run app.py
All logik ligger i kort.py och lagring.py, här finns bara det man ser på skärmen.

Utan inloggningsuppgifter körs appen i lokalt läge (demo, sparas i kort.json).
Med uppgifter för ett Google-ark körs den mot arket. Se README.md.
"""
import html

import streamlit as st

import kort as k
import lagring

st.set_page_config(page_title="Familjetavlan", page_icon="🗂️", layout="wide")

# ---------------------------------------------------------------- lagring


@st.cache_resource(show_spinner="Ansluter till lagringen …")
def hamta_lager():
    return lagring.valj_lager(st.secrets)


try:
    lager = hamta_lager()
except lagring.LagerFel as fel:
    st.title("🗂️ Familjetavlan")
    st.error(f"Kunde inte ansluta till Google Sheets: {fel}")
    st.caption(
        "Rätta uppgifterna och starta om, eller sätt miljövariabeln "
        "FAMILJETAVLA_LAGE=lokal för att prova appen utan arket."
    )
    st.stop()

try:
    kortlista = lager.alla()
except Exception as fel:  # nätverksfel mot Google m.m.
    st.error(f"Kunde inte läsa korten: {fel}")
    if st.button("Försök igen"):
        st.rerun()
    st.stop()


def utfor(atgard):
    """Kör en ändring mot lagringen och ritar om sidan. Visar fel på svenska."""
    try:
        atgard()
    except Exception as fel:
        st.error(f"Det gick inte att spara: {fel}")
        return
    st.rerun()


# ---------------------------------------------------------------- utseende


def css():
    """Stil för korten. Varje kort är en container med nyckel kort_<id>."""
    regler = [
        """
        .block-container { padding-top: 2rem; max-width: 1200px; }
        [class*="st-key-kort_"] {
            border-radius: 12px; padding: 0.7rem 0.9rem 0.5rem 0.9rem;
            margin-bottom: 0.4rem; color: %(text)s;
        }
        [class*="st-key-kort_"] .kort-datum {
            display: flex; justify-content: space-between; gap: 0.5rem;
            font-size: 0.8rem; opacity: 0.8; min-height: 1.1rem;
        }
        [class*="st-key-kort_"] .kort-titel { font-weight: 600; font-size: 1.05rem; margin: 0.2rem 0; }
        [class*="st-key-kort_"] .kort-besk { font-size: 0.92rem; margin-bottom: 0.3rem; }
        [class*="st-key-kort_"] .kort-meta { font-size: 0.8rem; opacity: 0.75; margin-bottom: 0.3rem; }
        /* Knapparna på kortet ligger i en rad, även på mobil */
        [class*="st-key-kort_"] [data-testid="stHorizontalBlock"] {
            flex-direction: row !important; flex-wrap: nowrap !important; gap: 0.4rem;
        }
        [class*="st-key-kort_"] [data-testid="stColumn"] { min-width: 0 !important; flex: 1 1 0 !important; }
        [class*="st-key-kort_"] button { width: 100%%; padding: 0.15rem 0.3rem; }
        """ % {"text": k.TEXTFARG}
    ]
    for kort in kortlista:
        f = k.farg(kort["typ"])
        regler.append(
            f".st-key-kort_{kort['id']} {{ background: {f['bakgrund']}; "
            f"border: 1px solid {f['kant']}; }}"
        )
    st.markdown("<style>" + "\n".join(regler) + "</style>", unsafe_allow_html=True)


def kort_html(kort):
    """HTML för kortets innehåll. All text från användare escapas."""
    def e(text):
        return html.escape(text)

    start = f"▶ {e(kort['startdatum'])}" if kort["startdatum"] else ""
    slut = f"⏰ {e(kort['slutdatum'])}" if kort["slutdatum"] else ""
    delar = [f"{e(kort['typ'])}"]
    if kort["ansvarig"]:
        delar.append(f"👤 {e(kort['ansvarig'])}")
    if kort["återkommande"]:
        delar.append(f"🔁 {e(kort['återkommande'])}")
    if kort["avslutad_datum"]:
        delar.append(f"✔ {e(kort['avslutad_datum'])}")
    besk = e(kort["beskrivning"]).replace("\n", "<br>")
    return (
        f'<div class="kort-datum"><span>{start}</span><span>{slut}</span></div>'
        f'<div class="kort-titel">{e(kort["titel"])}</div>'
        + (f'<div class="kort-besk">{besk}</div>' if besk else "")
        + f'<div class="kort-meta">{" · ".join(delar)}</div>'
    )


def _datum_eller_none(text):
    try:
        return k.tolka_datum(text)
    except ValueError:
        return None


@st.dialog("Redigera kort")
def redigera_dialog(kort):
    """Formulär för att ändra ett befintligt kort. Bara ändrade fält skrivs till arket."""
    id_ = kort["id"]
    typer = k.TYPER + ([kort["typ"]] if kort["typ"] not in k.TYPER else [])
    ansvariga = k.ANVANDARE + ([kort["ansvarig"]] if kort["ansvarig"] and kort["ansvarig"] not in k.ANVANDARE else [])
    with st.form(f"redigera_{id_}"):
        titel = st.text_input("Titel", value=kort["titel"])
        beskrivning = st.text_area("Beskrivning", value=kort["beskrivning"])
        typ = st.selectbox("Typ", typer, index=typer.index(kort["typ"]) if kort["typ"] in typer else 0)
        st.caption("Ett nytt kort som får typen påminnelse eller återkommande flyttas till Påbörjade. "
                   "Påbörjade och avslutade kort blir kvar där de är.")
        ansvarig = st.selectbox(
            "Ansvarig", ansvariga,
            index=ansvariga.index(kort["ansvarig"]) if kort["ansvarig"] in ansvariga else 0,
        )
        kol1, kol2 = st.columns(2)
        start = kol1.date_input("Startdatum (valfritt)", value=_datum_eller_none(kort["startdatum"]),
                                format="YYYY-MM-DD")
        slut = kol2.date_input("Slutdatum (valfritt)", value=_datum_eller_none(kort["slutdatum"]),
                               format="YYYY-MM-DD")
        ogiltiga = [t for t in (kort["startdatum"], kort["slutdatum"]) if t and _datum_eller_none(t) is None]
        if ogiltiga:
            st.caption("Ogiltigt datum i arket: " + ", ".join(ogiltiga)
                       + ". Välj ett nytt datum, annars töms fältet när du sparar.")
        aterkommande = st.text_input(
            "Återkommande (gäller bara typen återkommande, t.ex. 'varje måndag')",
            value=kort["återkommande"],
        )
        if st.form_submit_button("Spara"):
            try:
                andringar = lagring.redigera_kort(
                    lager, kort, titel, beskrivning, typ, ansvarig,
                    start or "", slut or "", aterkommande)
            except ValueError as fel:
                st.warning(str(fel))
            except Exception as fel:
                st.error(f"Det gick inte att spara: {fel}")
            else:
                st.rerun()


def _flytta(kort, steg):
    """Flyttar kortet genom att bara skriva fälten som ändras (status, avslutad_datum)."""
    andringar = k.flytt_andringar(kort, steg)
    if andringar:
        lager.andra_falt(kort["id"], andringar)


def rita_kort(kort):
    with st.container(key=f"kort_{kort['id']}"):
        st.markdown(kort_html(kort), unsafe_allow_html=True)
        vanster, hoger, redigera, radera = st.columns(4)
        if vanster.button("⬅️", key=f"v_{kort['id']}", disabled=not k.kan_flytta(kort, -1),
                          help="Flytta åt vänster"):
            utfor(lambda: _flytta(kort, -1))
        if hoger.button("➡️", key=f"h_{kort['id']}", disabled=not k.kan_flytta(kort, 1),
                        help="Flytta åt höger"):
            utfor(lambda: _flytta(kort, 1))
        if redigera.button("✏️", key=f"e_{kort['id']}", help="Redigera kortet"):
            redigera_dialog(kort)
        if radera.button("🗑️", key=f"r_{kort['id']}", help="Ta bort kortet"):
            utfor(lambda: lager.ta_bort(kort["id"]))


def rita_status(status):
    kort_i_status = k.i_status(kortlista, status)
    if status == "avslutad" and kort_i_status:
        if st.session_state.get("rensa_bekrafta"):
            st.warning(f"Ta bort alla {len(kort_i_status)} avslutade kort?")
            ja, nej = st.columns(2)
            if ja.button("Ja, rensa", key="rensa_ja"):
                st.session_state["rensa_bekrafta"] = False
                utfor(lambda: lager.ta_bort_flera(k.avslutade_id(kortlista)))
            if nej.button("Avbryt", key="rensa_nej"):
                st.session_state["rensa_bekrafta"] = False
                st.rerun()
        elif st.button("🧹 Rensa avslutade", key="rensa"):
            st.session_state["rensa_bekrafta"] = True
            st.rerun()
    if not kort_i_status:
        st.caption("Inga kort här.")
    for kort in kort_i_status:
        rita_kort(kort)


# ---------------------------------------------------------------- sidan

css()
st.title("🗂️ Familjetavlan")
st.caption(lager.beskrivning)

# --- Formulär för nytt kort ---
with st.expander("➕ Nytt kort"):
    with st.form("nytt_kort", clear_on_submit=True):
        titel = st.text_input("Titel")
        beskrivning = st.text_area("Beskrivning")
        typ = st.selectbox("Typ", k.TYPER)
        st.caption("Påminnelser och återkommande kort hamnar direkt i Påbörjade.")
        ansvarig = st.selectbox("Ansvarig", k.ANVANDARE)
        kol1, kol2 = st.columns(2)
        start = kol1.date_input("Startdatum (valfritt)", value=None, format="YYYY-MM-DD")
        slut = kol2.date_input("Slutdatum (valfritt)", value=None, format="YYYY-MM-DD")
        aterkommande = st.text_input(
            "Återkommande (bara för typen återkommande, t.ex. 'varje måndag')"
        )
        if st.form_submit_button("Lägg till"):
            try:
                nytt = k.nytt_kort(titel, beskrivning, typ, ansvarig, start or "",
                                   slut or "", aterkommande, skapad_av="appen")
            except ValueError as fel:
                st.warning(str(fel))
            else:
                utfor(lambda: lager.lagg_till(nytt))

# --- Vy: kolumner (dator) eller flikar (mobil) ---
vyer = ["Kolumner", "Flikar"]
vy = st.radio(
    "Visa som", vyer, horizontal=True,
    index=vyer.index(st.query_params.get("vy", "Kolumner")) if st.query_params.get("vy") in vyer else 0,
    help="Flikar passar bäst på mobilen.",
)
st.query_params["vy"] = vy
col_uppdatera, _ = st.columns([1, 3])
if col_uppdatera.button("🔄 Uppdatera"):
    st.rerun()

rubriker = [f"{k.STATUS_RUBRIK[s]} ({len(k.i_status(kortlista, s))})" for s in k.STATUSAR]
if vy == "Kolumner":
    for status, rubrik, ruta in zip(k.STATUSAR, rubriker, st.columns(len(k.STATUSAR))):
        with ruta:
            st.header(rubrik)
            rita_status(status)
else:
    for status, flik in zip(k.STATUSAR, st.tabs(rubriker)):
        with flik:
            rita_status(status)

# Kort med okänd status eller typ visas inte på tavlan, men ska inte försvinna obemärkt
okanda = [x for x in kortlista if x["status"] not in k.STATUSAR]
if okanda:
    st.warning(
        f"{len(okanda)} kort i arket har en okänd status och visas inte: "
        + ", ".join(x["titel"] for x in okanda)
    )
