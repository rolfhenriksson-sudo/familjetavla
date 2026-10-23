# 🗂️ Familjetavlan

En liten kortapp i Streamlit för aktiviteter: privata att-göra, påminnelser, jobb och
återkommande saker. Korten ligger i tre kolumner (**Nya**, **Påbörjade**, **Avslutade**)
och datan lagras i ett Google Sheet som även Fänrik Fjun kan läsa och skriva i.

*Familjetavlan är bara ett arbetsnamn.*

## Så fungerar det

- **Kort** har titel, beskrivning, typ, ansvarig samt valfritt startdatum (uppe till vänster)
  och slutdatum (uppe till höger).
- **Färg per typ:** privat = salviagrönt, påminnelse = dimblått, jobb = dammrosa,
  återkommande = ljus lavendel.
- **Påminnelser och återkommande kort** läggs alltid direkt i *Påbörjade*. Ett återkommande
  kort blir ett *nytt* kort varje gång, så gamla kort kan rensas bort från *Avslutade*.
- **Flytta** korten med pilknapparna, **redigera** med pennan ✏️, **ta bort** med papperskorgen,
  eller **🧹 Rensa avslutade**.
- **Redigera** öppnar en dialog där du kan ändra titel, beskrivning, typ, ansvarig, start- och
  slutdatum (slutdatum får inte ligga före startdatum) samt texten för återkommande kort.
  Bara de fält du ändrar skrivs, och bara på kortets egen rad i arket. Status, `avslutad_datum`,
  `förälder_id`, `ordning` och `skapad_av` rörs aldrig, och det Fjun ändrat i andra kolumner
  sedan appen läste arket skrivs inte över. Byter du typ på ett kort i *Nya* till påminnelse
  eller återkommande flyttas det till *Påbörjade*. Påbörjade och avslutade kort blir kvar
  där de är.
- **Flytt** skriver bara `status` (och `avslutad_datum` när kortet avslutas eller öppnas igen),
  inget annat på raden.
- **Mobil:** välj *Visa som → Flikar*, så får du en flik per kolumn i stället för tre kolumner.
- **Appen visar och ändrar bara arket.** Själva påminnelseutskicken sköter Fänrik Fjun
  med egna rutiner.

## Projekt och pass (version 2)

Ett **projekt** är ett kort med minst ett **pass** (underaktivitet). Pass är rader i samma flik
med `förälder_id` = projektets `id` och `ordning` = 1, 2, 3 …

- **På tavlan** syns bara projektkortet, med raden *"X av Y pass klara"* och en framstegsstapel.
  Passen visas inte som egna kort. Öppna **📋 Pass** på kortet för att se dem i ordning.
- **I passlistan** kan du bocka av ett pass (✅), markera det som påbörjat (🔄, tryck igen för att
  ångra), flytta det upp eller ner (⬆️ ⬇️), redigera titel och datum (✏️), ta bort det (🗑️) och
  lägga till ett nytt pass sist eller före ett annat. Pass har samma statusar som vanliga kort
  (`ny`, `påbörjad`, `avslutad`) och egna valfria start- och slutdatum.
- **Typ och färg ärvs** från projektet. Pass har inget typval, och ändrar du projektets typ får
  passen den nya typen.
- **Projektets status styrs av passen** och kan inte flyttas för hand (pilarna är avstängda):
  inget pass påbörjat eller klart = *Nya*, minst ett påbörjat eller klart men inte alla = *Påbörjade*,
  alla klara = *Avslutade*. Ett projekt av typen påminnelse eller återkommande ligger som minst
  *Påbörjade*. Statusen skrivs till arket när den ändras (och `avslutad_datum` när projektet
  avslutas eller öppnas igen), så att arket och appen visar samma sak.
- **Skapa projekt:** i *➕ Nytt kort* kan du skriva pass, ett per rad. Ett vanligt kort blir ett
  projekt när du lägger till dess första pass (fältet *Första pass* när du redigerar kortet).
  Ett projekt utan pass är bara ett vanligt kort. Tar du bort det sista passet blir projektet
  ett vanligt kort igen och behåller sin status.
- **Ta bort projekt** (🗑️) frågar först och tar bort projektet **tillsammans med alla dess pass**.
  **🧹 Rensa avslutade** tar bort avslutade kort och avslutade projekt med deras pass.
- **Trasig data:** ett pass vars projekt saknas visas som ett vanligt kort i sin egen status,
  och en rad längst ner talar om hur många pass som saknar projekt. Ett pass kan inte ha ett pass som förälder. Pass med
  ogiltig `ordning` hamnar sist. Appen kraschar inte.
- **Appen skriver bara fälten den ändrat,** på rätt rad. Det gäller även `förälder_id` och
  `ordning`: när ett pass sätts in före ett annat numreras bara de pass vars `ordning` ändras om.

### Så skriver Fjun projekt och pass

1. Skapa projektraden som ett vanligt kort (`förälder_id` och `ordning` tomma).
2. Lägg till en rad per pass: `förälder_id` = projektets `id`, `ordning` = `1`, `2`, `3` … (som text),
   `status` = `ny` (eller `påbörjad`/`avslutad` för pass som redan är igång eller klara),
   `typ` samma som projektet och `skapad_av` = `fjun`.
3. Projektradens `status` behöver Fjun inte sätta. Appen räknar ut den från passen vid nästa
   visning och skriver den till arket. Vill Fjun läsa statusen direkt: avslutad = alla pass avslutade.
4. Pass i pass stöds inte (ett pass har aldrig egna pass). Radera ett projekt genom att radera
   passen och därefter projektraden.


## Lösenordsskydd

Appen kan skyddas med ett enda gemensamt lösenord. Det läses ur hemligheten/miljövariabeln
`APP_LOSENORD` (samma mönster som övriga hemligheter).

- **Är `APP_LOSENORD` satt** visas bara en lösenordsruta. Inget annat innehåll visas och inget
  läses från arket förrän rätt lösenord är inskrivet. Lyckad inloggning gäller resten av
  sessionen (webbläsarfliken). Laddar du om sidan helt eller öppnar appen på nytt får du skriva
  lösenordet igen.
- **Är den inte satt** körs appen utan ruta, så lokalt läge och Codespaces fungerar som förut.
  Körs appen mot Google Sheets utan lösenord visas en diskret rad överst:
  *"⚠️ Ingen lösenordsskydd är aktivt."*
- Ett tomt värde räknas som "inte satt". Lösenordet jämförs med `hmac.compare_digest`.
  Lägg aldrig lösenordet i koden eller i repot.

**Codespaces:** *Settings → Codespaces → Secrets → New secret*, namn `APP_LOSENORD`, värdet är
lösenordet, och ge den åtkomst till repot `familjetavla`. Starta om codespacet.

**Streamlit Community Cloud:** appens *Settings → Secrets*, lägg till en rad (utanför
`[gcp_service_account]`, helst överst):

```toml
APP_LOSENORD = "ditt-lösenord"
```

**Lokalt:** samma rad i `.streamlit/secrets.toml`, eller `APP_LOSENORD=... streamlit run app.py`.

## Prova direkt i Codespaces (ingen inloggning)

1. Öppna repot på GitHub → **Code** → **Codespaces** → **Create codespace on main**.
2. Appen startar av sig själv. Öppna den från fliken **Ports** (porten 8501) med
   jordglobsikonen 🌐. Använd inte förhandsvisningen i editorn.
3. Utan inloggningsuppgifter körs appen i **lokalt läge** med fem exempelkort som sparas i
   `kort.json` (den filen ligger utanför git). Radera filen för att börja om.

Startar den inte: skriv `streamlit run app.py` i terminalen.

## Koppla till Google Sheets

Appen loggar in som ett *service account* (ett robotkonto hos Google). Du skapar det en gång.

### 1. Skapa service account

1. Gå till <https://console.cloud.google.com/> och skapa ett projekt (till exempel "Familjetavla").
2. Sök efter **Google Sheets API** under *APIs & Services → Library* och klicka **Enable**.
3. Gå till *APIs & Services → Credentials → Create credentials → Service account*.
   Ge det ett namn, till exempel `familjetavla`, och klicka dig igenom resten.
4. Öppna service accountet → fliken **Keys** → **Add key → Create new key → JSON**.
   En fil laddas ner. **Den är som ett lösenord: lägg den aldrig i repot.**
5. Öppna JSON-filen och kopiera värdet på `client_email`
   (ser ut som `familjetavla@projekt.iam.gserviceaccount.com`).

### 2. Dela arket med service accountet

Öppna arket **Familjetavla** → **Dela** → klistra in `client_email` → välj **Redigerare** → Skicka.
(Avmarkera "meddela personer" om Google frågar.)

Arkets id är den långa texten i webbadressen:
`https://docs.google.com/spreadsheets/d/` **`ARKETS-ID`** `/edit`.
Arket måste ha en flik som heter `Aktiviteter` med rubrikraden:

`id, titel, beskrivning, typ, status, ansvarig, startdatum, slutdatum, förälder_id, ordning, återkommande, skapad_av, avslutad_datum`

### 3. Lägg in uppgifterna

**Codespaces (rekommenderat):** på GitHub, *Settings → Codespaces → Secrets → New secret*.
Skapa två hemligheter och ge dem åtkomst till repot `familjetavla`:

| Namn | Värde |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | hela innehållet i JSON-filen |
| `FAMILJETAVLA_ARK_ID` | arkets id |

Starta sedan om codespacet (eller skapa ett nytt). Hemligheter läses bara in vid start.

**Streamlit Community Cloud (senare, för mobilen):** i appens *Settings → Secrets*, klistra in:

```toml
ark_id = "ARKETS-ID"
APP_LOSENORD = "ditt-lösenord"  # valfritt, se Lösenordsskydd

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "familjetavla@projekt.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

Värdena hämtar du från JSON-filen. Samma format fungerar lokalt i `.streamlit/secrets.toml`
(se `.streamlit/secrets.toml.exempel`; den riktiga filen sparas aldrig i git).

### 4. Kontrollera

Överst på sidan står det vilket läge appen kör: *"Lokalt läge (demo)"* eller
*"Ansluten till Google Sheets"*. Går något fel visas ett felmeddelande på svenska
(till exempel att arket inte är delat med service accountet).
Vill du tvinga lokalt läge trots att uppgifterna finns: sätt `FAMILJETAVLA_LAGE=lokal`.

## Fänrik Fjun

Fjun når arket via Sheets-connectorn med samma åtkomst som du, och kan lägga till kort
direkt i fliken `Aktiviteter`:

- `typ` är en av `privat`, `påminnelse`, `jobb`, `återkommande`.
- `status` är en av `ny`, `påbörjad`, `avslutad`. Påminnelser och återkommande kort läggs som `påbörjad`.
- Datum skrivs som `ÅÅÅÅ-MM-DD`. Skriv in värdena som text, så att Sheets inte omformaterar datumen.
- `id` kan vara vilken unik text som helst (appen använder åtta tecken, till exempel `a1b2c3d4`).
- `skapad_av`: skriv `fjun`. `ansvarig`: `Rolf`.

## Kod och tester

| Fil | Vad |
|---|---|
| `kort.py` | Ren logik: kort, flytt, färger, regler, validering, projekt och pass (status, ordning, framsteg) |
| `lagring.py` | `JsonLager` (lokalt) och `SheetsLager` (Google Sheets) med samma gränssnitt |
| `inloggning.py` | Lösenordsspärren (läser `APP_LOSENORD`, jämför i konstant tid) |
| `app.py` | Det som syns på skärmen |
| `test_*.py` | Tester med pytest. De körs automatiskt på GitHub (fliken *Actions*) |

Appen ändrar en rad i taget i arket (lägg till, ändra enskilda fält vid redigering, flytt och passbockning, ta bort) i stället för att skriva
om allt, så ändringar som Fjun gör samtidigt skrivs inte över.

Lokalt, om du vill: `pip install -r requirements.txt`, sedan `pytest -v` och `streamlit run app.py`.
