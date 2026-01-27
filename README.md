# Tagiato

CLI nástroj pro automatické přidání GPS souřadnic a AI-generovaných popisků k JPEG fotografiím exportovaným z Luminar.

## Instalace

```bash
pipx install tagiato
```

## Použití

### Základní workflow

```bash
# Zpracovat fotky s GPS z Google Timeline
tagiato enrich ~/Photos/Trip --timeline location-history.json

# Zkontrolovat výsledky
cat ~/Photos/Trip/descriptions.md

# Ověřit EXIF pomocí exiftool
exiftool ~/Photos/Trip/IMG_001.jpg
```

### Příkazy

```bash
# Celá pipeline - GPS matching, geocoding, AI popisky
tagiato enrich ~/Photos/Trip --timeline location-history.json

# S parametry
tagiato enrich ~/Photos/Trip \
  --timeline location-history.json \
  --max-time-gap 30 \
  --model sonnet \
  --thumbnail-size 1024

# Aplikace editovaného descriptions.md zpět do EXIF/XMP
tagiato apply ~/Photos/Trip

# Export do CSV nebo XMP
tagiato export ~/Photos/Trip --format csv
tagiato export ~/Photos/Trip --format xmp

# Kontrola stavu zpracování
tagiato status ~/Photos/Trip

# Nápověda
tagiato --help
```

## Workflow s ruční editací

1. Spusťte `tagiato enrich` pro zpracování fotek
2. Otevřete a upravte `descriptions.md` podle potřeby
3. Spusťte `tagiato apply` pro aplikaci změn zpět do EXIF a XMP

## Požadavky

- Python 3.8+
- [Claude CLI](https://github.com/anthropics/claude-cli) nainstalovaný a v PATH
- Google Timeline JSON export (volitelné, pro GPS matching)

## Výstupy

- **EXIF metadata** - GPS souřadnice a popisky zapsané do JPEG
- **XMP sidecar** - `.xmp` soubory pro každou fotku
- **descriptions.md** - Markdown soubor se všemi popisky, strukturovaný po dnech
- **CSV export** - Volitelný export do tabulkového formátu

## Licence

MIT
