"""Integrace s Claude CLI pro generování popisků."""

import json
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tagiato.core.exceptions import ClaudeNotFoundError
from tagiato.core.logger import log_call, log_result, log_info
from tagiato.models.location import GPSCoordinates


@dataclass
class DescriptionResult:
    """Výsledek od Claude."""

    description: str
    refined_gps: Optional[GPSCoordinates] = None
    gps_confidence: str = "unchanged"


class ClaudeDescriber:
    """Volá Claude CLI pro generování popisků fotek."""

    PROMPT_TEMPLATE = """Analyzuj obrázek na {thumbnail_path}.

Kontext:
- Přibližné místo dle GPS historie: {place_name}
- GPS (může být nepřesné): {lat}, {lng}
- Datum: {timestamp}

Úkoly:
1. Podívej se na fotografii a zkus ověřit/upřesnit pozici podle významných objektů (budovy, památky, krajina). Pokud rozpoznáš konkrétní místo, uveď přesnější GPS souřadnice.

2. Napiš 2-4 věty v češtině popisující fotografii:
   - Styl dle charakteru: krajina poeticky, architektura fakticky, lidé osobně
   - Popisek pro sociální sítě - chytlavý, zajímavý
   - Může obsahovat emotikon, ale nepřehánět
   - BEZ technických info (datum, fotoaparát)
   - Pokud není jasné co je na fotce, vrať prázdný popisek

Vrať POUZE JSON ve formátu (bez markdown code block):
{{"refined_gps": {{"lat": 50.123, "lng": 15.456}} nebo null, "gps_confidence": "high/medium/low/unchanged", "description": "Popisek fotografie..." nebo ""}}"""

    def __init__(self, model: str = "sonnet"):
        """
        Args:
            model: Model pro Claude (sonnet/opus/haiku)
        """
        self.model = model
        self._check_claude_available()

    def _check_claude_available(self) -> None:
        """Zkontroluje, že Claude CLI je dostupný."""
        if shutil.which("claude") is None:
            raise ClaudeNotFoundError()

    def describe(
        self,
        thumbnail_path: Path,
        place_name: Optional[str],
        coords: Optional[GPSCoordinates],
        timestamp: Optional[str],
    ) -> DescriptionResult:
        """Získá popis fotky od Claude.

        Args:
            thumbnail_path: Cesta k náhledu
            place_name: Název místa (může být None)
            coords: GPS souřadnice (mohou být None)
            timestamp: Čas pořízení (může být None)

        Returns:
            DescriptionResult s popiskem a případně upřesněnými GPS
        """
        log_call(
            "ClaudeDescriber",
            "describe",
            thumbnail=thumbnail_path.name,
            place=place_name,
            model=self.model,
        )

        prompt = self.PROMPT_TEMPLATE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            place_name=place_name or "neznámé",
            lat=f"{coords.latitude:.6f}" if coords else "neznámé",
            lng=f"{coords.longitude:.6f}" if coords else "neznámé",
            timestamp=timestamp or "neznámé",
        )

        log_info(f"claude --dangerously-skip-permissions --model {self.model} --print <prompt>")

        try:
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "--model", self.model, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                log_info(f"claude exited with code {result.returncode}")
                return DescriptionResult(description="")

            parsed = self._parse_response(result.stdout)
            log_result(
                "ClaudeDescriber",
                "describe",
                f"description={len(parsed.description)} chars, refined_gps={parsed.refined_gps is not None}",
            )
            return parsed

        except subprocess.TimeoutExpired:
            log_info("claude timeout after 120s")
            return DescriptionResult(description="")
        except Exception as e:
            log_info(f"claude error: {e}")
            return DescriptionResult(description="")

    def _parse_response(self, response: str) -> DescriptionResult:
        """Parsuje JSON odpověď od Claude."""
        try:
            # Očistit odpověď od případných markdown bloků
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                # Odstranit první a poslední řádek (```json a ```)
                response = "\n".join(lines[1:-1])

            data = json.loads(response)

            refined_gps = None
            if data.get("refined_gps"):
                gps_data = data["refined_gps"]
                refined_gps = GPSCoordinates(
                    latitude=float(gps_data["lat"]),
                    longitude=float(gps_data["lng"]),
                )

            return DescriptionResult(
                description=data.get("description", ""),
                refined_gps=refined_gps,
                gps_confidence=data.get("gps_confidence", "unchanged"),
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Pokud nelze parsovat JSON, zkusit použít celou odpověď jako popisek
            # (pro případ, že Claude vrátí jen text)
            if response and not response.startswith("{"):
                return DescriptionResult(description=response.strip())
            return DescriptionResult(description="")

    def generate_trip_summary(
        self, photos_info: list, places: list, date_range: tuple
    ) -> str:
        """Vygeneruje AI souhrn cesty.

        Args:
            photos_info: Seznam informací o fotkách
            places: Seznam navštívených míst
            date_range: Tuple (start_date, end_date)

        Returns:
            Souhrn cesty
        """
        log_call(
            "ClaudeDescriber",
            "generate_trip_summary",
            photos=len(photos_info),
            places=len(places),
        )

        start_date, end_date = date_range
        places_str = ", ".join(places[:10])  # Max 10 míst

        log_info(f"claude --dangerously-skip-permissions --model {self.model} --print <summary_prompt>")

        prompt = f"""Na základě těchto informací napiš krátký (2-3 věty) poetický souhrn cesty v češtině:

Období: {start_date} - {end_date}
Navštívená místa: {places_str}
Počet fotek: {len(photos_info)}

Souhrn by měl být osobní a evokativní, ne jen výčet faktů. Vrať POUZE text souhrnu, bez uvozovek."""

        try:
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "--model", self.model, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return result.stdout.strip()

        except (subprocess.TimeoutExpired, Exception):
            pass

        return ""
