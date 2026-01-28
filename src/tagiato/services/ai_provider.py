"""Abstrakce pro AI providery (Claude, Gemini)."""

import json
import subprocess
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tagiato.core.logger import log_call, log_result, log_info, log_prompt, log_response
from tagiato.models.location import GPSCoordinates


@dataclass
class DescriptionResult:
    """Výsledek generování popisku."""
    description: str
    refined_gps: Optional[GPSCoordinates] = None
    gps_confidence: str = "unchanged"


@dataclass
class LocationResult:
    """Výsledek lokalizace."""
    gps: Optional[GPSCoordinates] = None
    confidence: str = "low"
    location_name: str = ""
    reasoning: str = ""


# Společné prompt šablony
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

DESCRIBE_PROMPT_TEMPLATE = """Jsi stručný glosátor a cestovatel. Tvým úkolem je k fotce napsat "mikro-popisek" (caption).

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


class AIProvider(ABC):
    """Abstraktní třída pro AI providery."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Název providera."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Zkontroluje dostupnost CLI nástroje."""
        pass

    @abstractmethod
    def describe(
        self,
        thumbnail_path: Path,
        place_name: Optional[str],
        coords: Optional[GPSCoordinates],
        timestamp: Optional[str],
    ) -> DescriptionResult:
        """Vygeneruje popisek pro fotku."""
        pass

    @abstractmethod
    def locate(
        self,
        thumbnail_path: Path,
        timestamp: Optional[str],
    ) -> LocationResult:
        """Určí GPS pozici fotky."""
        pass


def _parse_json_response(response: str) -> dict:
    """Parsuje JSON z odpovědi AI (s podporou markdown bloků)."""
    response = response.strip()

    # Najít JSON blok v markdown
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

    # Pokud stále není JSON, zkusit najít { ... }
    if not response.startswith("{"):
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            response = response[json_start:json_end]

    return json.loads(response)


class ClaudeProvider(AIProvider):
    """Claude CLI provider."""

    def __init__(self, model: str = "sonnet"):
        self.model = model

    @property
    def name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def _run_claude(self, prompt: str) -> Optional[str]:
        """Spustí Claude CLI s promptem."""
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
                return None

            log_response(result.stdout)
            return result.stdout

        except subprocess.TimeoutExpired:
            log_info("claude timeout after 120s")
            return None
        except Exception as e:
            log_info(f"claude error: {e}")
            return None

    def describe(
        self,
        thumbnail_path: Path,
        place_name: Optional[str],
        coords: Optional[GPSCoordinates],
        timestamp: Optional[str],
    ) -> DescriptionResult:
        log_call("ClaudeProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamicky sestavit kontextové řádky
        context_lines = []
        if coords:
            context_lines.append(f"- GPS: {coords.latitude:.6f}, {coords.longitude:.6f}")
        if place_name:
            context_lines.append(f"- Místo (hrubý odhad): {place_name}")
        if timestamp:
            context_lines.append(f"- Datum: {timestamp}")

        prompt = DESCRIBE_PROMPT_TEMPLATE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
        )

        response = self._run_claude(prompt)
        if not response:
            return DescriptionResult(description="")

        try:
            data = _parse_json_response(response)
            refined_gps = None
            if data.get("refined_gps"):
                gps_data = data["refined_gps"]
                refined_gps = GPSCoordinates(
                    latitude=float(gps_data["lat"]),
                    longitude=float(gps_data["lng"]),
                )

            result = DescriptionResult(
                description=data.get("description", ""),
                refined_gps=refined_gps,
                gps_confidence=data.get("gps_confidence", "unchanged"),
            )
            log_result("ClaudeProvider", "describe", f"description={len(result.description)} chars")
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Fallback - použít celou odpověď jako popisek
            if response and not response.strip().startswith("{"):
                return DescriptionResult(description=response.strip())
            return DescriptionResult(description="")

    def locate(
        self,
        thumbnail_path: Path,
        timestamp: Optional[str],
    ) -> LocationResult:
        log_call("ClaudeProvider", "locate", thumbnail=thumbnail_path.name, model=self.model)

        prompt = LOCATE_PROMPT_TEMPLATE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            timestamp=timestamp or "neznámé",
        )

        response = self._run_claude(prompt)
        if not response:
            return LocationResult()

        try:
            data = _parse_json_response(response)
            gps = None
            if data.get("gps"):
                gps_data = data["gps"]
                gps = GPSCoordinates(
                    latitude=float(gps_data["lat"]),
                    longitude=float(gps_data["lng"]),
                )

            result = LocationResult(
                gps=gps,
                confidence=data.get("confidence", "low"),
                location_name=data.get("location_name", ""),
                reasoning=data.get("reasoning", ""),
            )
            log_result("ClaudeProvider", "locate", f"gps={result.gps is not None}, confidence={result.confidence}")
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return LocationResult()


class GeminiProvider(AIProvider):
    """Google Gemini CLI provider."""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def _run_gemini(self, prompt: str) -> Optional[str]:
        """Spustí Gemini CLI s promptem."""
        log_info(f"gemini --yolo --model {self.model} <prompt>")
        log_prompt(prompt)

        try:
            result = subprocess.run(
                ["gemini", "--yolo", "--model", self.model, "--output-format", "text", prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                log_info(f"gemini exited with code {result.returncode}")
                log_info(f"stderr: {result.stderr}")
                return None

            log_response(result.stdout)
            return result.stdout

        except subprocess.TimeoutExpired:
            log_info("gemini timeout after 120s")
            return None
        except Exception as e:
            log_info(f"gemini error: {e}")
            return None

    def describe(
        self,
        thumbnail_path: Path,
        place_name: Optional[str],
        coords: Optional[GPSCoordinates],
        timestamp: Optional[str],
    ) -> DescriptionResult:
        log_call("GeminiProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamicky sestavit kontextové řádky
        context_lines = []
        if coords:
            context_lines.append(f"- GPS: {coords.latitude:.6f}, {coords.longitude:.6f}")
        if place_name:
            context_lines.append(f"- Místo (hrubý odhad): {place_name}")
        if timestamp:
            context_lines.append(f"- Datum: {timestamp}")

        prompt = DESCRIBE_PROMPT_TEMPLATE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
        )

        response = self._run_gemini(prompt)
        if not response:
            return DescriptionResult(description="")

        try:
            data = _parse_json_response(response)
            refined_gps = None
            if data.get("refined_gps"):
                gps_data = data["refined_gps"]
                refined_gps = GPSCoordinates(
                    latitude=float(gps_data["lat"]),
                    longitude=float(gps_data["lng"]),
                )

            result = DescriptionResult(
                description=data.get("description", ""),
                refined_gps=refined_gps,
                gps_confidence=data.get("gps_confidence", "unchanged"),
            )
            log_result("GeminiProvider", "describe", f"description={len(result.description)} chars")
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            if response and not response.strip().startswith("{"):
                return DescriptionResult(description=response.strip())
            return DescriptionResult(description="")

    def locate(
        self,
        thumbnail_path: Path,
        timestamp: Optional[str],
    ) -> LocationResult:
        log_call("GeminiProvider", "locate", thumbnail=thumbnail_path.name, model=self.model)

        prompt = LOCATE_PROMPT_TEMPLATE.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            timestamp=timestamp or "neznámé",
        )

        response = self._run_gemini(prompt)
        if not response:
            return LocationResult()

        try:
            data = _parse_json_response(response)
            gps = None
            if data.get("gps"):
                gps_data = data["gps"]
                gps = GPSCoordinates(
                    latitude=float(gps_data["lat"]),
                    longitude=float(gps_data["lng"]),
                )

            result = LocationResult(
                gps=gps,
                confidence=data.get("confidence", "low"),
                location_name=data.get("location_name", ""),
                reasoning=data.get("reasoning", ""),
            )
            log_result("GeminiProvider", "locate", f"gps={result.gps is not None}, confidence={result.confidence}")
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return LocationResult()


def get_provider(provider_name: str, model: Optional[str] = None) -> AIProvider:
    """Factory funkce pro vytvoření AI providera.

    Args:
        provider_name: "claude" nebo "gemini"
        model: Volitelný model (default: sonnet pro Claude, gemini-2.0-flash pro Gemini)

    Returns:
        Instance AIProvider

    Raises:
        ValueError: Neznámý provider
    """
    if provider_name == "claude":
        return ClaudeProvider(model=model or "sonnet")
    elif provider_name == "gemini":
        return GeminiProvider(model=model or "gemini-2.0-flash")
    else:
        raise ValueError(f"Neznámý AI provider: {provider_name}")


def get_available_providers() -> list[str]:
    """Vrátí seznam dostupných providerů."""
    available = []
    if ClaudeProvider().is_available():
        available.append("claude")
    if GeminiProvider().is_available():
        available.append("gemini")
    return available
