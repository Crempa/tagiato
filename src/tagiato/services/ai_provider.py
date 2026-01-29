"""Abstrakce pro AI providery (Claude, Gemini, OpenAI Codex)."""

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
{user_hint_line}

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
{context_lines}{user_hint_line}

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
        custom_prompt: Optional[str] = None,
        location_name: Optional[str] = None,
        user_hint: str = "",
    ) -> DescriptionResult:
        """Vygeneruje popisek pro fotku."""
        pass

    @abstractmethod
    def locate(
        self,
        thumbnail_path: Path,
        timestamp: Optional[str],
        custom_prompt: Optional[str] = None,
        user_hint: str = "",
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
        custom_prompt: Optional[str] = None,
        location_name: Optional[str] = None,
        user_hint: str = "",
    ) -> DescriptionResult:
        log_call("ClaudeProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamicky sestavit kontextové řádky
        context_lines = []
        if coords:
            context_lines.append(f"- GPS: {coords.latitude:.6f}, {coords.longitude:.6f}")
        if location_name:
            context_lines.append(f"- Lokalizované místo: {location_name}")
        if place_name:
            context_lines.append(f"- Místo (hrubý odhad): {place_name}")
        if timestamp:
            context_lines.append(f"- Datum: {timestamp}")

        # User hint line
        if user_hint.strip():
            user_hint_line = f"- Uživatel k tomu dodává: {user_hint}"
        else:
            user_hint_line = ""

        template = custom_prompt or DESCRIBE_PROMPT_TEMPLATE
        prompt = template.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
        )

        response = self._run_claude(prompt)
        if not response:
            return DescriptionResult(description="")

        try:
            data = _parse_json_response(response)
            result = DescriptionResult(description=data.get("description", ""))
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
        custom_prompt: Optional[str] = None,
        user_hint: str = "",
    ) -> LocationResult:
        log_call("ClaudeProvider", "locate", thumbnail=thumbnail_path.name, model=self.model)

        # User hint line
        if user_hint.strip():
            user_hint_line = f"- Uživatel k tomu dodává: {user_hint}"
        else:
            user_hint_line = ""

        template = custom_prompt or LOCATE_PROMPT_TEMPLATE
        prompt = template.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            timestamp=timestamp or "neznámé",
            user_hint_line=user_hint_line,
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

    def __init__(self, model: str = "flash"):
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
        custom_prompt: Optional[str] = None,
        location_name: Optional[str] = None,
        user_hint: str = "",
    ) -> DescriptionResult:
        log_call("GeminiProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamicky sestavit kontextové řádky
        context_lines = []
        if coords:
            context_lines.append(f"- GPS: {coords.latitude:.6f}, {coords.longitude:.6f}")
        if location_name:
            context_lines.append(f"- Lokalizované místo: {location_name}")
        if place_name:
            context_lines.append(f"- Místo (hrubý odhad): {place_name}")
        if timestamp:
            context_lines.append(f"- Datum: {timestamp}")

        # User hint line
        if user_hint.strip():
            user_hint_line = f"- Uživatel k tomu dodává: {user_hint}"
        else:
            user_hint_line = ""

        template = custom_prompt or DESCRIBE_PROMPT_TEMPLATE
        prompt = template.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
        )

        response = self._run_gemini(prompt)
        if not response:
            return DescriptionResult(description="")

        try:
            data = _parse_json_response(response)
            result = DescriptionResult(description=data.get("description", ""))
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
        custom_prompt: Optional[str] = None,
        user_hint: str = "",
    ) -> LocationResult:
        log_call("GeminiProvider", "locate", thumbnail=thumbnail_path.name, model=self.model)

        # User hint line
        if user_hint.strip():
            user_hint_line = f"- Uživatel k tomu dodává: {user_hint}"
        else:
            user_hint_line = ""

        template = custom_prompt or LOCATE_PROMPT_TEMPLATE
        prompt = template.format(
            thumbnail_path=str(thumbnail_path.absolute()),
            timestamp=timestamp or "neznámé",
            user_hint_line=user_hint_line,
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


class OpenAIProvider(AIProvider):
    """OpenAI Codex CLI provider."""

    def __init__(self, model: str = "o3"):
        self.model = model

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def _run_codex(self, prompt: str, image_path: Path) -> Optional[str]:
        """Spustí Codex CLI s promptem a obrázkem."""
        log_info(f"codex exec --model {self.model} --image {image_path.name} <prompt>")
        log_prompt(prompt)

        try:
            result = subprocess.run(
                [
                    "codex", "exec",
                    "--model", self.model,
                    "--image", str(image_path.absolute()),
                    "--full-auto",
                    prompt,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                log_info(f"codex exited with code {result.returncode}")
                log_info(f"stderr: {result.stderr}")
                return None

            log_response(result.stdout)
            return result.stdout

        except subprocess.TimeoutExpired:
            log_info("codex timeout after 120s")
            return None
        except Exception as e:
            log_info(f"codex error: {e}")
            return None

    def describe(
        self,
        thumbnail_path: Path,
        place_name: Optional[str],
        coords: Optional[GPSCoordinates],
        timestamp: Optional[str],
        custom_prompt: Optional[str] = None,
        location_name: Optional[str] = None,
        user_hint: str = "",
    ) -> DescriptionResult:
        log_call("OpenAIProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamicky sestavit kontextové řádky
        context_lines = []
        if coords:
            context_lines.append(f"- GPS: {coords.latitude:.6f}, {coords.longitude:.6f}")
        if location_name:
            context_lines.append(f"- Lokalizované místo: {location_name}")
        if place_name:
            context_lines.append(f"- Místo (hrubý odhad): {place_name}")
        if timestamp:
            context_lines.append(f"- Datum: {timestamp}")

        # User hint line
        if user_hint.strip():
            user_hint_line = f"- Uživatel k tomu dodává: {user_hint}"
        else:
            user_hint_line = ""

        template = custom_prompt or DESCRIBE_PROMPT_TEMPLATE
        prompt = template.format(
            thumbnail_path="[obrázek přiložen přes --image]",
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
        )

        response = self._run_codex(prompt, thumbnail_path)
        if not response:
            return DescriptionResult(description="")

        try:
            data = _parse_json_response(response)
            result = DescriptionResult(description=data.get("description", ""))
            log_result("OpenAIProvider", "describe", f"description={len(result.description)} chars")
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            if response and not response.strip().startswith("{"):
                return DescriptionResult(description=response.strip())
            return DescriptionResult(description="")

    def locate(
        self,
        thumbnail_path: Path,
        timestamp: Optional[str],
        custom_prompt: Optional[str] = None,
        user_hint: str = "",
    ) -> LocationResult:
        log_call("OpenAIProvider", "locate", thumbnail=thumbnail_path.name, model=self.model)

        # User hint line
        if user_hint.strip():
            user_hint_line = f"- Uživatel k tomu dodává: {user_hint}"
        else:
            user_hint_line = ""

        template = custom_prompt or LOCATE_PROMPT_TEMPLATE
        prompt = template.format(
            thumbnail_path="[obrázek přiložen přes --image]",
            timestamp=timestamp or "neznámé",
            user_hint_line=user_hint_line,
        )

        response = self._run_codex(prompt, thumbnail_path)
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
            log_result("OpenAIProvider", "locate", f"gps={result.gps is not None}, confidence={result.confidence}")
            return result

        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return LocationResult()


def get_provider(provider_name: str, model: Optional[str] = None) -> AIProvider:
    """Factory funkce pro vytvoření AI providera.

    Args:
        provider_name: "claude", "gemini" nebo "openai"
        model: Volitelný model (default: sonnet pro Claude, flash pro Gemini, o3 pro OpenAI)

    Returns:
        Instance AIProvider

    Raises:
        ValueError: Neznámý provider
    """
    if provider_name == "claude":
        return ClaudeProvider(model=model or "sonnet")
    elif provider_name == "gemini":
        return GeminiProvider(model=model or "flash")
    elif provider_name == "openai":
        return OpenAIProvider(model=model or "o3")
    else:
        raise ValueError(f"Neznámý AI provider: {provider_name}")


def get_available_providers() -> list[str]:
    """Vrátí seznam dostupných providerů."""
    available = []
    if ClaudeProvider().is_available():
        available.append("claude")
    if GeminiProvider().is_available():
        available.append("gemini")
    if OpenAIProvider().is_available():
        available.append("openai")
    return available
