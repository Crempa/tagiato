# Tagiato

Nástroj pro automatické přidání GPS souřadnic a AI-generovaných popisků k JPEG fotografiím exportovaným z Luminar.

## Instalace

```bash
pipx install tagiato
```

## Použití

```bash
# Spustit webové rozhraní pro složku s fotkami
tagiato ~/Photos/Trip

# S GPS daty z Google Timeline
tagiato ~/Photos/Trip --timeline location-history.json

# S vlastním portem a bez automatického otevření prohlížeče
tagiato ~/Photos/Trip --port 3000 --no-browser

# Volba AI providera a modelu
tagiato ~/Photos/Trip --describe-provider gemini --describe-model flash
```

## Webové rozhraní

Po spuštění se otevře prohlížeč s galérií fotek, kde můžete:

- Procházet a filtrovat fotky
- Generovat AI popisky jednotlivě nebo hromadně
- Lokalizovat fotky pomocí AI (detekce místa z fotky)
- Editovat GPS souřadnice a popisky
- Přiřazovat GPS z Google Timeline podle časových razítek
- Ukládat metadata zpět do EXIF

## Požadavky

- Python 3.10+
- [Claude CLI](https://github.com/anthropics/claude-cli), [Gemini CLI](https://github.com/google-gemini/gemini-cli) nebo [OpenAI Codex CLI](https://github.com/openai/codex) nainstalovaný a v PATH
- Google Timeline JSON export (volitelné, pro GPS matching)

## Licence

MIT
