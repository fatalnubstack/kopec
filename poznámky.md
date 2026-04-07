# Bořen Tracker — poznámky a nápady

## Kontext projektu
- Neoficiální hobby projekt, ceduli instaluješ sám
- Cílová skupina: místní sportovci i turisté (obojí)
- Provoz na Synology NAS DS923+ přes Docker, port 8090

---

## Co rozvíjet (prioritní)

### Výsledková karta po výstupu
Po dokončení výstupu zobrazit hezky vypadající kartu kterou jde sdílet jako screenshot:
- Jméno výstupce
- Čas výstupu (velké, čitelné)
- Pořadí v žebříčku (all-time)
- Název kopce + datum
- Musí dobře vypadat na mobilu i jako screenshot

### Věrohodnost žebříčku
Teď může kdokoliv zadat cokoliv — "Usain Bolt", nereálné časy apod.
Možnosti do budoucna:
- Admin může označit záznam jako "neověřeno" / "podezřelý"
- Automatická detekce nereálně rychlých časů (pod X minut → upozornění v adminu)
- Rekordní časy vyžadují admin schválení před zobrazením v top 3

---

## Co rozvíjet (později)

### Nativní sdílení na mobilu
Web Share API — tlačítko "Sdílet" co otevře nativní share sheet na iOS/Android.
Funguje v Safari na iOS bez instalace appky.

### Fyzická cedule
Mimo kód, ale patří do projektu:
- Laminovaný tisk nebo gravírování (odolnost vůči počasí)
- Krytka nebo zasklení QR kódu
- Umístění: pata kopce (start) + vrchol (cíl)

---

## Záměrně vynechat (zatím)

- Registrace uživatelů / přihlašování
- Více kopců
- Generované obrázky (Wrapped styl) — složité, zatím zbytečné
- Mapa, fotky, animace

---

## Technické poznámky

- Backend: FastAPI + SQLite (SQLAlchemy)
- Čas se počítá server-side — funguje i po zavření prohlížeče
- climb_id v localStorage spojuje start a finish
- Varování pro uživatele: nespouštět v soukromém okně (localStorage se smaže)
- Admin: HTTP Basic Auth, heslo přes env proměnnou ADMIN_PASSWORD
