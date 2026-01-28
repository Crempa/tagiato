"""Integrace s Claude CLI pro generování popisků."""

import json
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tagiato.core.exceptions import ClaudeNotFoundError
from tagiato.core.logger import log_call, log_result, log_info, log_prompt, log_response
from tagiato.models.location import GPSCoordinates


@dataclass
class DescriptionResult:
    """Výsledek od Claude."""

    description: str
    refined_gps: Optional[GPSCoordinates] = None
    gps_confidence: str = "unchanged"


@dataclass
class LocationResult:
    """Výsledek lokalizace od Claude."""

    gps: Optional[GPSCoordinates] = None
    confidence: str = "low"
    location_name: str = ""
    reasoning: str = ""


class ClaudeDescriber:
    """Volá Claude CLI pro generování popisků fotek."""

    LOCATE_PROMPT_TEMPLATE = """Jsi expert na geolokalizaci fotografií. Tvým úkolem je určit PŘESNÉ GPS souřadnice místa na fotce.

    Vstupní data:
    - Cesta k náhledu: {thumbnail_path}
    - Datum pořízení: {timestamp}

    INSTRUKCE:
    1. Analyzuj fotku a pokus se identifikovat konkrétní místo (budovu, památku, ulici, park, atd.)
    2. Pokud bezpečně poznáš místo, vrať jeho přesné GPS souřadnice (střed budovy/památky)
    3. Pokud místo nepoznáš s jistotou, vrať null
    4. Buď konzervativní - lepší je vrátit null než špatné souřadnice

    ÚROVEŇ JISTOTY:
    - "high": Jednoznačně poznávám konkrétní budovu/památku (např. Eiffelovka, Petronas Towers)
    - "medium": Poznávám typ místa a oblast, ale ne přesnou budovu
    - "low": Nejsem si jistý, jen haduji

    VÝSTUP JSON:
    {{
        "gps": {{"lat": float, "lng": float}} nebo null,
        "confidence": "high" | "medium" | "low",
        "location_name": "Název rozpoznaného místa",
        "reasoning": "Stručné vysvětlení, proč jsi místo poznal/nepoznal"
    }}
    """

    PROMPT_TEMPLATE_BASE = """Jsi stručný glosátor a cestovatel. Tvým úkolem je k fotce napsat "mikro-popisek" (caption).

    Vstupní data:
    - Cesta k náhledu: {thumbnail_path}
{context_lines}
    INSTRUKCE PRO GPS:
    - Pokud bezpečně poznáš konkrétní památku/budovu, oprav GPS na její střed. Jinak nech null.

    INSTRUKCE PRO TEXT (POPISEK):
    Musíš dodržet tento striktní formát:
    1. První věta: Musí obsahovat PŘESNÝ NÁZEV MÍSTA nebo objektu (nominativ).
    2. Druhá věta: Jedna technická/historická zajímavost nebo "hard fact" související s tím, co je na fotce.
    3. NIC VÍC. Žádné úvody "Nacházíme se...", žádné pocity.

    OMEZENÍ:
    - Maximální délka: 2 krátké věty (cca 20-30 slov).
    - Styl: Encyklopedický, telegrafický, přímočarý.

    PŘÍKLADY VÝSTUPU (Takhle to má vypadat):
    - "Petronas Towers, Kuala Lumpur. Ve 41. patře je spojuje dvoupodlažní most, který není pevně ukotven kvůli výkyvům budov."
    - "Chrám Sagrada Família. Gaudí na ní pracoval 43 let a věděl, že se dokončení nedožije."
    - "Pláž Reynisfjara, Island. Černý písek vznikl erozí vulkanické horniny při kontaktu žhavé lávy s oceánem."

    VÝSTUP JSON:
    {{
    "refined_gps": {{"lat": float, "lng": float}} nebo null,
    "gps_confidence": "high" | "medium" | "low",
    "location_name_refined": "Název místa",
    "description": "Tvůj text..."
    }}
    """
    
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

        # Dynamicky sestavit kontextové řádky - jen když existují
        context_lines = []
        if coords:
            context_lines.append(f"    - GPS: {coords.latitude:.6f}, {coords.longitude:.6f}")
        if place_name:
            context_lines.append(f"    - Místo (hrubý odhad): {place_name}")
        if timestamp:
            context_lines.append(f"    - Datum: {timestamp}")

        prompt = self.PROMPT_TEMPLATE_BASE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
        )

        log_info(f"claude --dangerously-skip-permissions --model {self.model} --print <prompt>")
        log_prompt(prompt)

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

            log_response(result.stdout)
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

    def locate(
        self,
        thumbnail_path: Path,
        place_name: Optional[str],
        coords: Optional[GPSCoordinates],
        timestamp: Optional[str],
    ) -> LocationResult:
        """Pokusí se určit přesnou GPS pozici fotky pomocí AI.

        Args:
            thumbnail_path: Cesta k náhledu
            place_name: Název místa (může být None)
            coords: Aktuální GPS souřadnice (mohou být None)
            timestamp: Čas pořízení (může být None)

        Returns:
            LocationResult s GPS a úrovní jistoty
        """
        log_call(
            "ClaudeDescriber",
            "locate",
            thumbnail=thumbnail_path.name,
            place=place_name,
            model=self.model,
        )

        prompt = self.LOCATE_PROMPT_TEMPLATE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            timestamp=timestamp or "neznámé",
        )

        log_info(f"claude --dangerously-skip-permissions --model {self.model} --print <locate_prompt>")
        log_prompt(prompt)

        try:
            result = subprocess.run(
                ["claude", "--dangerously-skip-permissions", "--model", self.model, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                log_info(f"claude exited with code {result.returncode}")
                return LocationResult()

            log_response(result.stdout)
            parsed = self._parse_location_response(result.stdout)
            log_result(
                "ClaudeDescriber",
                "locate",
                f"gps={parsed.gps is not None}, confidence={parsed.confidence}",
            )
            return parsed

        except subprocess.TimeoutExpired:
            log_info("claude timeout after 120s")
            return LocationResult()
        except Exception as e:
            log_info(f"claude error: {e}")
            return LocationResult()

    def _parse_location_response(self, response: str) -> LocationResult:
        """Parsuje JSON odpověď pro lokalizaci."""
        try:
            response = response.strip()

            # Najít JSON blok
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                if response[start:start+1] == "\n":
                    start += 1
                else:
                    newline = response.find("\n", start)
                    if newline > start:
                        start = newline + 1
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()

            if not response.startswith("{"):
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    response = response[json_start:json_end]

            data = json.loads(response)

            gps = None
            if data.get("gps"):
                gps_data = data["gps"]
                gps = GPSCoordinates(
                    latitude=float(gps_data["lat"]),
                    longitude=float(gps_data["lng"]),
                )

            return LocationResult(
                gps=gps,
                confidence=data.get("confidence", "low"),
                location_name=data.get("location_name", ""),
                reasoning=data.get("reasoning", ""),
            )

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return LocationResult()

    def _parse_response(self, response: str) -> DescriptionResult:
        """Parsuje JSON odpověď od Claude."""
        try:
            # Očistit odpověď od případných markdown bloků a textu okolo JSON
            response = response.strip()

            # Najít JSON blok v markdown (```json ... ```)
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                # Obecný code block
                start = response.find("```") + 3
                # Přeskočit případný jazyk na prvním řádku
                if response[start:start+1] == "\n":
                    start += 1
                else:
                    newline = response.find("\n", start)
                    if newline > start:
                        start = newline + 1
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()

            # Pokud stále není JSON, zkusit najít { ... }
            if not response.startswith("{"):
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    response = response[json_start:json_end]

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
