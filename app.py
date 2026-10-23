"""Familjetavlan – webbgränssnittet.

Starta med:  streamlit run app.py
All logik ligger i kort.py och lagring.py, här finns bara det man ser på skärmen.

Utan inloggningsuppgifter körs appen i lokalt läge (demo, sparas i kort.json).
Med uppgifter för ett Google-ark körs den mot arket. Se README.md.
"""
import html

import streamlit as st

import inloggning
import kort as k
import lagring

st.set_page_config(page_title="Familjetavlan", page_icon="🗂️", layout="wide")

# ---------------------------------------------------------------- inloggning


def losenordsparr():
    """Stoppar sidan tills rätt lösenord skrivits. Körs före all annan kod, och därmed före
    anslutningen till lagret. Är APP_LOSENORD inte satt visas ingen ruta."""
    losenord = inloggning.las_losenord(st.secrets)
    if losenord is None:
        if lagring.ar_sheets_lage(st.secrets):
            st.caption("⚠️ Ingen lösenordsskydd är aktivt.")
        return
    if st.session_state.get("inloggad") is True:
        return
    st.title("🔒 Familjetavlan")
    with st.form("inloggning"):
        inmatat = st.text_input("Lösenord", type="password")
        skickat = st.form_submit_button("Logga in")
    if skickat:
        if inloggning.losenord_ratt(inmatat, losenord):
            st.session_state["inloggad"] = True
            st.rerun()
        st.error("Fel lösenord.")
    st.stop()


losenordsparr()

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


# Projektens status följer passen. Skrivs till arket om den ändrats (t.ex. av Fjun)
kortlista, synkfel = lagring.synka_alla(lager, kortlista)
tavla = k.tavelkort(kortlista)  # det som syns på tavlan: pass visas inte som egna kort
if synkfel:
    st.warning("Kunde inte uppdatera projektstatus i arket: " + "; ".join(synkfel))


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
        [class*="st-key-kort_"] .framsteg { margin: 0.3rem 0 0.4rem 0; }
        [class*="st-key-kort_"] .framsteg-text { font-size: 0.8rem; opacity: 0.85; }
        [class*="st-key-kort_"] .framsteg-bar { height: 6px; border-radius: 3px; background: rgba(255,255,255,0.65); margin-top: 2px; }
        [class*="st-key-kort_"] .framsteg-fyll { height: 100%%; border-radius: 3px; background: rgba(47,59,53,0.55); }
        [class*="st-key-kort_"] [class*="st-key-pass_"] { border-top: 1px solid rgba(47,59,53,0.15); padding-top: 0.4rem; margin-top: 0.3rem; }
        [class*="st-key-kort_"] .pass-titel { font-weight: 600; font-size: 0.95rem; }
        [class*="st-key-kort_"] .pass-klart { text-decoration: line-through; opacity: 0.7; }
        [class*="st-key-kort_"] .pass-meta { font-size: 0.78rem; opacity: 0.75; }
        """ % {"text": k.TEXTFARG}
    ]
    for kort in tavla:
        f = k.farg(kort["typ"])
        regler.append(
            f".st-key-kort_{kort['id']} {{ background: {f['bakgrund']}; "
            f"border: 1px solid {f['kant']}; }}"
        )
    st.markdown("<style>" + "\n".join(regler) + "</style>", unsafe_allow_html=True)


def framsteg_html(pass_lista):
    klara, totalt = k.framsteg(pass_lista)
    procent = round(100 * klara / totalt) if totalt else 0
    return (f'<div class="framsteg"><div class="framsteg-text">{html.escape(k.framsteg_text(pass_lista))}</div>'
            f'<div class="framsteg-bar"><div class="framsteg-fyll" style="width:{procent}%"></div></div></div>')


def kort_html(kort, pass_lista=(), foraldralost=False):
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
    if foraldralost:
        delar.append(f"⚠️ pass utan projekt (förälder_id {e(kort['förälder_id'])})")
    besk = e(kort["beskrivning"]).replace("\n", "<br>")
    return (
        f'<div class="kort-datum"><span>{start}</span><span>{slut}</span></div>'
        f'<div class="kort-titel">{e(kort["titel"])}</div>'
        + (f'<div class="kort-besk">{besk}</div>' if besk else "")
        + (framsteg_html(pass_lista) if pass_lista else "")
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
    ar_proj = k.ar_projekt(kort, kortlista)
    kan_bli_projekt = not ar_proj and not k.ar_pass(kort)
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
        forsta_pass = ""
        if kan_bli_projekt:
            forsta_pass = st.text_input(
                "Första pass (valfritt)",
                help="Fyll i en titel för att göra kortet till ett projekt. Fler pass lägger du till på kortet.")
        elif ar_proj:
            st.caption("Projektets status följer passen. Pass lägger du till och ändrar på kortet.")
        if st.form_submit_button("Spara"):
            try:
                andringar = lagring.redigera_projekt(
                    lager, kort, titel, beskrivning, typ, ansvarig,
                    start or "", slut or "", aterkommande)
                if forsta_pass.strip():
                    lagring.lagg_till_pass(lager, kort["id"], forsta_pass)
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


@st.dialog("Redigera pass")
def redigera_pass_dialog(pass_):
    """Titel, beskrivning och datum för ett pass. Typ, status och ordning rörs inte."""
    with st.form(f"redigera_pass_{pass_['id']}"):
        titel = st.text_input("Titel", value=pass_["titel"])
        beskrivning = st.text_area("Beskrivning (valfritt)", value=pass_["beskrivning"])
        kol1, kol2 = st.columns(2)
        start = kol1.date_input("Startdatum (valfritt)", value=_datum_eller_none(pass_["startdatum"]),
                                format="YYYY-MM-DD")
        slut = kol2.date_input("Slutdatum (valfritt)", value=_datum_eller_none(pass_["slutdatum"]),
                               format="YYYY-MM-DD")
        if st.form_submit_button("Spara"):
            try:
                lagring.redigera_pass(lager, pass_["id"], titel, beskrivning, start or "", slut or "")
            except ValueError as fel:
                st.warning(str(fel))
            except Exception as fel:
                st.error(f"Det gick inte att spara: {fel}")
            else:
                st.rerun()


PASS_IKON = {"ny": "⬜", "påbörjad": "🔄", "avslutad": "✅"}


def pass_html(pass_):
    e = html.escape
    klass = "pass-titel pass-klart" if pass_["status"] == "avslutad" else "pass-titel"
    delar = []
    if pass_["startdatum"]:
        delar.append(f"▶ {e(pass_['startdatum'])}")
    if pass_["slutdatum"]:
        delar.append(f"⏰ {e(pass_['slutdatum'])}")
    if pass_["avslutad_datum"] and pass_["status"] == "avslutad":
        delar.append(f"✔ {e(pass_['avslutad_datum'])}")
    besk = e(pass_["beskrivning"]).replace("\n", "<br>")
    return (f'<div class="{klass}">{PASS_IKON.get(pass_["status"], "⬜")} {e(pass_["titel"])}</div>'
            + (f'<div class="pass-meta">{" · ".join(delar)}</div>' if delar else "")
            + (f'<div class="pass-meta">{besk}</div>' if besk else ""))


def _oppen(projekt_id):
    st.session_state[f"oppen_{projekt_id}"] = True


def rita_pass(projekt, passen):
    """Passen i ordning med knappar: klart, påbörjat, upp, ned, redigera, ta bort. Plus formulär för nytt pass."""
    for nr, p in enumerate(passen):
        pid = p["id"]
        with st.container(key=f"pass_{pid}"):
            st.markdown(pass_html(p), unsafe_allow_html=True)
            klar, pagar, upp, ned, red, bort = st.columns(6)
            if klar.button("✅", key=f"pk_{pid}", help="Markera som klart (igen för att ångra)"):
                _oppen(projekt["id"])
                nystatus = "ny" if p["status"] == "avslutad" else "avslutad"
                utfor(lambda: lagring.satt_pass_status(lager, pid, nystatus))
            if pagar.button("🔄", key=f"pp_{pid}", disabled=p["status"] == "avslutad",
                            help="Markera som påbörjat (igen för att ångra)"):
                _oppen(projekt["id"])
                nystatus = "ny" if p["status"] == "påbörjad" else "påbörjad"
                utfor(lambda: lagring.satt_pass_status(lager, pid, nystatus))
            if upp.button("⬆️", key=f"pu_{pid}", disabled=nr == 0, help="Flytta upp"):
                _oppen(projekt["id"])
                utfor(lambda: lagring.flytta_pass(lager, pid, -1))
            if ned.button("⬇️", key=f"pn_{pid}", disabled=nr == len(passen) - 1, help="Flytta ned"):
                _oppen(projekt["id"])
                utfor(lambda: lagring.flytta_pass(lager, pid, 1))
            if red.button("✏️", key=f"pe_{pid}", help="Redigera passet"):
                _oppen(projekt["id"])
                redigera_pass_dialog(p)
            if bort.button("🗑️", key=f"pr_{pid}", help="Ta bort passet"):
                _oppen(projekt["id"])
                utfor(lambda: lagring.ta_bort_pass(lager, pid))
    with st.form(f"nytt_pass_{projekt['id']}", clear_on_submit=True):
        titel = st.text_input("Nytt pass", placeholder="Titel på passet")
        platser = [""] + [p["id"] for p in passen]
        titlar = {p["id"]: p["titel"] for p in passen}
        fore = st.selectbox("Placering", platser,
                            format_func=lambda i: "Sist" if not i else f"Före: {titlar[i]}")
        kol1, kol2 = st.columns(2)
        start = kol1.date_input("Startdatum (valfritt)", value=None, format="YYYY-MM-DD")
        slut = kol2.date_input("Slutdatum (valfritt)", value=None, format="YYYY-MM-DD")
        if st.form_submit_button("Lägg till pass"):
            _oppen(projekt["id"])
            try:
                lagring.lagg_till_pass(lager, projekt["id"], titel, startdatum=start or "",
                                       slutdatum=slut or "", fore_id=fore or None)
            except ValueError as fel:
                st.warning(str(fel))
            except Exception as fel:
                st.error(f"Det gick inte att spara: {fel}")
            else:
                st.rerun()


def rita_kort(kort):
    passen = k.passen_till(kortlista, kort["id"])
    ar_proj = bool(passen)
    with st.container(key=f"kort_{kort['id']}"):
        st.markdown(kort_html(kort, passen, k.ar_foraldralost(kort, kortlista)),
                    unsafe_allow_html=True)
        if st.session_state.get("radera_projekt") == kort["id"]:
            st.warning(f"Ta bort projektet och alla {len(passen)} pass?")
            ja, nej = st.columns(2)
            if ja.button("Ja, ta bort", key=f"rja_{kort['id']}"):
                st.session_state["radera_projekt"] = None
                utfor(lambda: lagring.ta_bort_projekt(lager, kort["id"]))
            if nej.button("Avbryt", key=f"rnej_{kort['id']}"):
                st.session_state["radera_projekt"] = None
                st.rerun()
        else:
            vanster, hoger, redigera, radera = st.columns(4)
            hjalp = "Statusen följer passen" if ar_proj else None
            if vanster.button("⬅️", key=f"v_{kort['id']}",
                              disabled=ar_proj or not k.kan_flytta(kort, -1),
                              help=hjalp or "Flytta åt vänster"):
                utfor(lambda: _flytta(kort, -1))
            if hoger.button("➡️", key=f"h_{kort['id']}",
                            disabled=ar_proj or not k.kan_flytta(kort, 1),
                            help=hjalp or "Flytta åt höger"):
                utfor(lambda: _flytta(kort, 1))
            if redigera.button("✏️", key=f"e_{kort['id']}", help="Redigera kortet"):
                redigera_dialog(kort)
            if radera.button("🗑️", key=f"r_{kort['id']}",
                             help="Ta bort projektet och alla dess pass" if ar_proj else "Ta bort kortet"):
                if ar_proj:
                    st.session_state["radera_projekt"] = kort["id"]
                    st.rerun()
                else:
                    utfor(lambda: lager.ta_bort(kort["id"]))
        if ar_proj:
            with st.expander("📋 Pass", expanded=bool(st.session_state.get(f"oppen_{kort['id']}"))):
                rita_pass(kort, passen)


def rita_status(status):
    kort_i_status = k.i_status(tavla, status)
    if status == "avslutad" and kort_i_status:
        if st.session_state.get("rensa_bekrafta"):
            antal_pass = sum(len(k.passen_till(kortlista, x["id"])) for x in kort_i_status)
            extra = f" och deras {antal_pass} pass" if antal_pass else ""
            st.warning(f"Ta bort alla {len(kort_i_status)} avslutade kort{extra}?")
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
        pass_text = st.text_area(
            "Pass (valfritt, ett per rad)",
            help="Skriv ett pass per rad för att skapa ett projekt. Projektets status följer passen.",
        )
        if st.form_submit_button("Lägg till"):
            try:
                # Allt valideras innan något skrivs (skapa_projekt skriver först efteråt)
                k.nytt_kort(titel, beskrivning, typ, ansvarig, start or "", slut or "", aterkommande)
            except ValueError as fel:
                st.warning(str(fel))
            else:
                utfor(lambda: lagring.skapa_projekt(
                    lager, titel, beskrivning, typ, ansvarig, start or "", slut or "",
                    aterkommande, pass_text.splitlines()))

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

rubriker = [f"{k.STATUS_RUBRIK[s]} ({len(k.i_status(tavla, s))})" for s in k.STATUSAR]
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
okanda = [x for x in tavla if x["status"] not in k.STATUSAR]
if okanda:
    st.warning(
        f"{len(okanda)} kort i arket har en okänd status och visas inte: "
        + ", ".join(x["titel"] for x in okanda)
    )

# Pass vars projekt saknas visas som vanliga kort, men ska inte passera obemärkta
foraldralosa = [x for x in tavla if k.ar_foraldralost(x, kortlista)]
if foraldralosa:
    st.caption(
        f"{len(foraldralosa)} pass saknar projekt (förälder_id pekar på ett kort som inte finns) "
        "och visas som vanliga kort: " + ", ".join(x["titel"] for x in foraldralosa)
    )
