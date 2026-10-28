---
name: avsluta-dagen
description: Avsluta arbetsdagen på Macen — visa öppna appar, stäng de som operatören väljer och lås skärmen. Använd vid "avsluta dagen", "stäng ner", "jag går hem" eller liknande.
tools: list_running_apps, quit_app, lock_screen
---

# Avsluta dagen

Ett recept över befintliga verktyg. Skillen ger inga behörigheter: varje
`quit_app` går via godkännandekortet som vanligt.

## Steg

1. Anropa `list_running_apps`.
2. Visa listan och fråga vilka appar som ska stängas. Föreslå inte att stänga
   terminalen eller editorn som chatten körs i (Terminal, iTerm2, Ghostty,
   Warp, Code) — då avslutas Bridget mitt i receptet. Går det inte att fråga,
   till exempel i ett engångsanrop, sluta efter listan.
3. Stäng varje vald app med `quit_app` och `force: false`. Använd namnet exakt
   som `list_running_apps` gav det.
4. Om `quit_app` svarar `failed`: säg vilken app och varför. Föreslå
   `force: true` bara om operatören uttryckligen vill tvinga avslut, och säg
   att osparat arbete i den appen då försvinner.
5. Fråga om skärmen ska låsas. Anropa `lock_screen` bara vid ja, och sist —
   efter låsningen kan operatören inte läsa svaret.
6. Sammanfatta före låsningen: stängda appar, appar som inte stängdes och varför.

## Regler

- Stäng aldrig en app som operatören inte har valt.
- Gissa inte appnamn och stäng inte "allt" på eget initiativ.
- Ett `not_running`-svar är inget fel: appen var redan stängd.
