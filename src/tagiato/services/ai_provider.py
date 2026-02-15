"""Abstraction for AI providers (Claude, Gemini, OpenAI Codex)."""

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
    """Result of description generation."""
    description: str


@dataclass
class LocationResult:
    """Result of location detection."""
    gps: Optional[GPSCoordinates] = None
    confidence: str = "low"
    location_name: str = ""
    reasoning: str = ""


# Shared prompt templates
LOCATE_PROMPT_TEMPLATE = """Jsi expert na geolokalizaci. Tvým úkolem je určit PŘESNÉ GPS souřadnice místa.

Vstupní data:
{image_line}- Datum pořízení: {timestamp}
{user_hint_line}

INSTRUKCE:
1. Na základě dostupných informací se pokus identifikovat konkrétní místo (budovu, památku, ulici, park, atd.)
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

DESCRIBE_PROMPT_TEMPLATE = """Jsi stručný glosátor a cestovatel. Tvým úkolem je napsat "mikro-popisek" (caption) k danému místu.

Vstupní data:
{image_line}{context_lines}{user_hint_line}
{nearby_descriptions_line}
INSTRUKCE PRO TEXT (POPISEK):
Musíš dodržet tento striktní formát:
1. První věta: Musí obsahovat PŘESNÝ NÁZEV MÍSTA nebo objektu (nominativ).
2. Druhá věta: Jedna technická/historická zajímavost nebo "hard fact" související s daným místem.
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
    """Abstract class for AI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check availability of the CLI tool."""
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
        nearby_descriptions: Optional[list[str]] = None,
    ) -> DescriptionResult:
        """Generate a description for a photo."""
        pass

    @abstractmethod
    def locate(
        self,
        thumbnail_path: Path,
        timestamp: Optional[str],
        custom_prompt: Optional[str] = None,
        user_hint: str = "",
    ) -> LocationResult:
        """Determine the GPS position of a photo."""
        pass


def _parse_json_response(response: str) -> dict:
    """Parse JSON from AI response (with markdown block support)."""
    response = response.strip()

    # Find JSON block in markdown
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

    # If still not JSON, try to find { ... }
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
        """Run Claude CLI with a prompt."""
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
        nearby_descriptions: Optional[list[str]] = None,
    ) -> DescriptionResult:
        log_call("ClaudeProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamically build context lines
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

        # Nearby descriptions context
        if nearby_descriptions:
            descriptions_text = "\n".join(f"- {d}" for d in nearby_descriptions)
            nearby_line = f"""EXISTUJÍCÍ POPISKY Z OKOLÍ:
{descriptions_text}

DŮLEŽITÉ: NIKDY neopakuj informace z výše uvedených popisků!
Vyber JINÝ zajímavý fakt o daném místě.
"""
        else:
            nearby_line = ""

        template = custom_prompt or DESCRIBE_PROMPT_TEMPLATE
        image_line = f"- Analyzuj tento obrázek: {thumbnail_path.absolute()}\n"
        prompt = template.format(
            image_line=image_line,
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
            nearby_descriptions_line=nearby_line,
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
            # Fallback - use the entire response as the description
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
        image_line = f"- Analyzuj tento obrázek: {thumbnail_path.absolute()}\n"
        prompt = template.format(
            image_line=image_line,
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
        """Run Gemini CLI with a prompt."""
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
        nearby_descriptions: Optional[list[str]] = None,
    ) -> DescriptionResult:
        log_call("GeminiProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamically build context lines
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

        # Nearby descriptions context
        if nearby_descriptions:
            descriptions_text = "\n".join(f"- {d}" for d in nearby_descriptions)
            nearby_line = f"""EXISTUJÍCÍ POPISKY Z OKOLÍ:
{descriptions_text}

DŮLEŽITÉ: NIKDY neopakuj informace z výše uvedených popisků!
Vyber JINÝ zajímavý fakt o daném místě.
"""
        else:
            nearby_line = ""

        template = custom_prompt or DESCRIBE_PROMPT_TEMPLATE
        image_line = f"- Analyzuj tento obrázek: {thumbnail_path.absolute()}\n"
        prompt = template.format(
            image_line=image_line,
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
            nearby_descriptions_line=nearby_line,
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
        image_line = f"- Analyzuj tento obrázek: {thumbnail_path.absolute()}\n"
        prompt = template.format(
            image_line=image_line,
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
        """Run Codex CLI with a prompt and image."""
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
        nearby_descriptions: Optional[list[str]] = None,
    ) -> DescriptionResult:
        log_call("OpenAIProvider", "describe", thumbnail=thumbnail_path.name, model=self.model)

        # Dynamically build context lines
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

        # Nearby descriptions context
        if nearby_descriptions:
            descriptions_text = "\n".join(f"- {d}" for d in nearby_descriptions)
            nearby_line = f"""EXISTUJÍCÍ POPISKY Z OKOLÍ:
{descriptions_text}

DŮLEŽITÉ: NIKDY neopakuj informace z výše uvedených popisků!
Vyber JINÝ zajímavý fakt o daném místě.
"""
        else:
            nearby_line = ""

        template = custom_prompt or DESCRIBE_PROMPT_TEMPLATE
        image_line = "- Analyzuj přiložený obrázek\n"
        prompt = template.format(
            image_line=image_line,
            context_lines="\n".join(context_lines) + "\n" if context_lines else "",
            user_hint_line=user_hint_line,
            nearby_descriptions_line=nearby_line,
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
        image_line = "- Analyzuj přiložený obrázek\n"
        prompt = template.format(
            image_line=image_line,
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
    """Factory function for creating an AI provider.

    Args:
        provider_name: "claude", "gemini" or "openai"
        model: Optional model (default: sonnet for Claude, flash for Gemini, o3 for OpenAI)

    Returns:
        AIProvider instance

    Raises:
        ValueError: Unknown provider
    """
    if provider_name == "claude":
        return ClaudeProvider(model=model or "sonnet")
    elif provider_name == "gemini":
        return GeminiProvider(model=model or "flash")
    elif provider_name == "openai":
        return OpenAIProvider(model=model or "o3")
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")


def get_available_providers() -> list[str]:
    """Return a list of available providers."""
    available = []
    if ClaudeProvider().is_available():
        available.append("claude")
    if GeminiProvider().is_available():
        available.append("gemini")
    if OpenAIProvider().is_available():
        available.append("openai")
    return available
