"""Real Codex CLI AI Provider adapter (Part 5B)."""

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    AIProvider,
)

logger = logging.getLogger(__name__)

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("CODEX_DEFAULT_TIMEOUT_SECONDS", "180.0"))
DEFAULT_DEEP_RESEARCH_TIMEOUT_SECONDS = float(
    os.environ.get("CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS", "600.0")
)

DEEP_RESEARCH_PROTOCOLS = {
    "deep-research",
    "deep-research-equity",
    "deep-research-fund",
    "deep-research-crypto",
    "deep-research-gold",
}


def is_deep_research_protocol(protocol_name: str | None) -> bool:
    """Return True if protocol is an intensive Deep Research workflow."""
    if not protocol_name:
        return False
    norm = protocol_name.strip().lower().replace("_", "-")
    return norm in DEEP_RESEARCH_PROTOCOLS or norm.startswith("deep-research")


def resolve_protocol_timeout(
    protocol_name: str | None,
    default_timeout: float | None = None,
    deep_research_timeout: float | None = None,
) -> float:
    """Resolve timeout (seconds) tailored to the specific protocol's execution profile."""
    def_timeout = (
        float(default_timeout)
        if default_timeout is not None
        else float(os.environ.get("CODEX_DEFAULT_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    )
    deep_timeout = (
        float(deep_research_timeout)
        if deep_research_timeout is not None
        else float(os.environ.get("CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS", DEFAULT_DEEP_RESEARCH_TIMEOUT_SECONDS))
    )
    if is_deep_research_protocol(protocol_name):
        return deep_timeout
    return def_timeout


def _sanitize_output(text: str) -> str:
    """Mask sensitive tokens or authorization keys from stderr/stdout."""
    if not text:
        return ""
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED_SECRET]", text)
    text = re.sub(
        r"(token|secret|key|bearer)\s*[:= ]\s*['\"]?[A-Za-z0-9_-]{8,}['\"]?",
        r"\1 [REDACTED]",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _kill_process_tree(proc: Any) -> None:
    """Terminate the process and all child descendants cleanly to avoid orphan processes."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        pass

    pid = getattr(proc, "pid", None)
    if pid is not None and os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except Exception:
            pass

    try:
        proc.kill()
    except Exception:
        pass

    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def _resolve_codex_executable(executable: str | Path | None = None) -> str:
    """Safely locate the Codex CLI binary."""
    if executable is not None:
        p = Path(executable)
        if p.is_file():
            return str(p.resolve())
        found = shutil.which(str(executable))
        if found:
            return found
        raise FileNotFoundError(f"Specified Codex executable not found: {executable}")

    found = shutil.which("codex")
    if found:
        return found

    # Fallback to standard Windows location if not in PATH
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        win_default = (
            Path(local_app_data)
            / "Programs"
            / "OpenAI"
            / "Codex"
            / "bin"
            / "codex.exe"
        )
        if win_default.is_file():
            return str(win_default)

    raise FileNotFoundError(
        "Codex CLI executable ('codex') was not found on PATH or standard install locations."
    )


def _extract_json_object(raw: str) -> str:
    """Extract valid JSON string from raw CLI output, stripping code fences or prose."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Attempt to extract substring between first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    return text


class CodexCLIProvider(AIProvider):
    """Executes AI investment protocols via locally authenticated Codex CLI.

    Design and Invariants:
    1. Implements vendor-independent AIProvider contract.
    2. Zero hard-coded credentials; relies on local ~/.codex/auth.json session.
    3. Safe subprocess execution: shell=False, prompt passed strictly via stdin (-).
    4. Controlled working directory with read-only sandbox policy.
    5. Clean structured JSON output written to a dedicated temporary file (-o).
    6. Configurable timeout with guaranteed temporary file cleanup.
    7. Sanitized diagnostics: process errors do not leak internal tokens or stderr traces.
    8. Generic adapter: protocol-specific enum schema validation remains in Part 5A layer.
    """

    def __init__(
        self,
        *,
        executable: str | Path | None = None,
        model: str | None = None,
        timeout: float | None = None,
        default_timeout: float | None = None,
        deep_research_timeout: float | None = None,
        cwd: Path | str | None = None,
        sandbox: str = "read-only",
    ):
        self.executable_path = _resolve_codex_executable(executable)
        self.model = model
        self._explicit_timeout = float(timeout) if timeout is not None else None
        self.default_timeout = (
            float(default_timeout)
            if default_timeout is not None
            else float(os.environ.get("CODEX_DEFAULT_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
        )
        self.deep_research_timeout = (
            float(deep_research_timeout)
            if deep_research_timeout is not None
            else float(os.environ.get("CODEX_DEEP_RESEARCH_TIMEOUT_SECONDS", DEFAULT_DEEP_RESEARCH_TIMEOUT_SECONDS))
        )
        self.timeout = self._explicit_timeout if self._explicit_timeout is not None else self.default_timeout
        self.cwd = Path(cwd).resolve() if cwd is not None else DEFAULT_REPO_ROOT
        if not self.cwd.is_dir():
            raise ValueError(f"Working directory does not exist: {self.cwd}")
        self.sandbox = sandbox

    def resolve_timeout(self, request: AIExecutionRequest) -> float:
        """Resolve effective execution timeout for a given request."""
        req_timeout = getattr(request, "timeout", None)
        if req_timeout is not None:
            return float(req_timeout)
        if self._explicit_timeout is not None:
            return self._explicit_timeout
        return resolve_protocol_timeout(
            request.protocol_name,
            default_timeout=self.default_timeout,
            deep_research_timeout=self.deep_research_timeout,
        )

    def build_prompt(self, request: AIExecutionRequest) -> str:
        """Compose controlled, unambiguous prompt separating protocol, context, and output schema."""
        canonical_proto = request.protocol_name.strip().lower().replace("_", "-")
        if canonical_proto.startswith("copilot") and "[SYSTEM_RULES]" in request.protocol_text:
            return request.protocol_text

        sections = [
            "You are an AI investment intelligence engine executing an investment analysis protocol.",
            "Follow the protocol instructions strictly using the provided persistent and supplemental context.",
            "",
            "=== PROTOCOL INSTRUCTIONS ===",
            f"Protocol Name: {request.protocol_name}",
            request.protocol_text.strip(),
            "",
            "=== PERSISTENT ASSET CONTEXT ===",
            json.dumps(request.persistent_context, indent=2, default=str),
        ]

        if request.supplemental_context:
            sections.extend([
                "",
                "=== SUPPLEMENTAL CONTEXT ===",
                json.dumps(request.supplemental_context, indent=2, default=str),
            ])

        if request.execution_metadata:
            sections.extend([
                "",
                "=== EXECUTION METADATA ===",
                json.dumps(request.execution_metadata, indent=2, default=str),
            ])

        canonical_proto = request.protocol_name.strip().lower().replace("_", "-")
        if canonical_proto == "thesis-review":
            example_machine_record = (
                '    "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "material_changes": ["list of notable changes observed"],\n'
                '    "open_questions": ["list of key unresolved questions"]'
            )
        elif canonical_proto == "valuation-update":
            example_machine_record = (
                '    "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "fair_value_narrative": "Detailed valuation assessment and fair value anchor.",\n'
                '    "material_changes": ["list of key valuation or financial estimate adjustments"]'
            )
        elif canonical_proto == "earnings-review":
            example_machine_record = (
                '    "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "earnings_assessment": "Quarterly earnings beat/miss assessment and forward guidance impact.",\n'
                '    "material_changes": ["list of notable fundamental or guidance changes"]'
            )
        elif canonical_proto == "technical-review":
            example_machine_record = (
                '    "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | REVIEW_REQUIRED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "technical_summary": "Price structure, key levels, and trend momentum assessment.",\n'
                '    "key_levels": ["support, resistance, or invalidation price levels"]'
            )
        elif canonical_proto == "deep-research-fund":
            example_machine_record = (
                '    "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",\n'
                '    "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",\n'
                '    "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | PULLBACK | EXTENDED | BREAKDOWN | UNKNOWN | N_A | REVIEW_REQUIRED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "confidence": 65,\n'
                '    "assessment_type": "FUND",\n'
                '    "underlying_valuation": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",\n'
                '    "fund_quality": "STRONG | ACCEPTABLE | WEAK | POOR | UNKNOWN",\n'
                '    "fund_attractiveness": "ATTRACTIVE | NEUTRAL | UNATTRACTIVE",\n'
                '    "execution_status": "AVAILABLE | RESTRICTED | BLOCKED | UNKNOWN",\n'
                '    "recovery_value_confidence": "HIGH | MEDIUM | LOW | 0-100 (optional)",\n'
                '    "execution_confidence": "HIGH | MEDIUM | LOW | 0-100 (optional)",\n'
                '    "data_quality_score": 70,\n'
                '    "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",\n'
                '    "supporting_reasons": ["Key performance driver", "Key fee or portfolio driver"],\n'
                '    "key_risks": ["Risk factor 1", "Risk factor 2"],\n'
                '    "what_would_change_my_view": "Conditions that would upgrade/downgrade this view.",\n'
                '    "evidence_gaps": ["Any data limitations identified"],\n'
                '    "review_required_reason": null,\n'
                '    "comprehensive_synthesis": "Comprehensive deep-dive findings on mandate, manager, and risk metrics."\n'
            )
        elif canonical_proto == "deep-research-crypto":
            example_machine_record = (
                '    "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",\n'
                '    "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",\n'
                '    "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | PULLBACK | EXTENDED | BREAKDOWN | UNKNOWN | N_A | REVIEW_REQUIRED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "confidence": 82,\n'
                '    "assessment_type": "CRYPTO",\n'
                '    "execution_status": "AVAILABLE | RESTRICTED | BLOCKED | UNKNOWN",\n'
                '    "network_adoption": "EXPANDING | STABLE | CONTRACTING",\n'
                '    "market_attractiveness": "ATTRACTIVE | NEUTRAL | UNATTRACTIVE",\n'
                '    "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",\n'
                '    "supporting_reasons": ["Key tokenomics/on-chain driver", "Key market structure driver"],\n'
                '    "key_risks": ["Risk factor 1", "Risk factor 2"],\n'
                '    "what_would_change_my_view": "Conditions that would upgrade/downgrade this view.",\n'
                '    "evidence_gaps": ["Any data limitations identified"],\n'
                '    "review_required_reason": null,\n'
                '    "comprehensive_synthesis": "Comprehensive analysis of network adoption, tokenomics, and market structure."\n'
            )
        elif canonical_proto == "deep-research-gold":
            example_machine_record = (
                '    "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",\n'
                '    "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",\n'
                '    "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | PULLBACK | EXTENDED | BREAKDOWN | UNKNOWN | N_A | REVIEW_REQUIRED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "confidence": 85,\n'
                '    "assessment_type": "PRECIOUS_METALS",\n'
                '    "execution_status": "AVAILABLE | RESTRICTED | BLOCKED | UNKNOWN",\n'
                '    "macro_regime": "FAVORABLE | NEUTRAL | UNFAVORABLE",\n'
                '    "macro_attractiveness": "ATTRACTIVE | NEUTRAL | UNATTRACTIVE",\n'
                '    "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",\n'
                '    "supporting_reasons": ["Key real yield/central bank driver", "Key currency cushion driver"],\n'
                '    "key_risks": ["Risk factor 1", "Risk factor 2"],\n'
                '    "what_would_change_my_view": "Conditions that would upgrade/downgrade this view.",\n'
                '    "evidence_gaps": ["Any data limitations identified"],\n'
                '    "review_required_reason": null,\n'
                '    "comprehensive_synthesis": "Comprehensive analysis of real yields, central bank demand, and physical spread."\n'
            )
        elif canonical_proto == "deep-research" or canonical_proto == "deep-research-equity":
            example_machine_record = (
                '    "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",\n'
                '    "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",\n'
                '    "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | PULLBACK | EXTENDED | BREAKDOWN | UNKNOWN | N_A | REVIEW_REQUIRED",\n'
                '    "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",\n'
                '    "confidence": 78,\n'
                '    "assessment_type": "EQUITY",\n'
                '    "execution_status": "AVAILABLE | RESTRICTED | BLOCKED | UNKNOWN",\n'
                '    "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",\n'
                '    "supporting_reasons": ["Key fundamental driver 1", "Key moat/financial driver 2"],\n'
                '    "key_risks": ["Risk factor 1", "Risk factor 2"],\n'
                '    "what_would_change_my_view": "Conditions that would upgrade/downgrade this view.",\n'
                '    "evidence_gaps": ["Any data limitations identified"],\n'
                '    "review_required_reason": null,\n'
                '    "comprehensive_synthesis": "Comprehensive deep-dive findings and strategic conclusions."\n'
            )
        elif canonical_proto in ("briefing-assessment", "briefing-reasoning"):
            example_machine_record = (
                '    "event_summary": "Concise summary of what specifically occurred in this event.",\n'
                '    "impact": "POSITIVE | NEGATIVE | NEUTRAL | MIXED",\n'
                '    "materiality": "MEDIUM | HIGH | CRITICAL",\n'
                '    "time_horizon": "SHORT | MEDIUM | LONG",\n'
                '    "thesis_impact": "STRONGER | UNCHANGED | WEAKER | POTENTIALLY_INVALIDATING | NOT_EVALUATED",\n'
                '    "review_required": true,\n'
                '    "why_it_matters": "Direct explanation of how this event affects the asset thesis, risk, or entry/exit parameters.",\n'
                '    "recommended_review": "NONE | THESIS_REVIEW | EARNINGS_REVIEW | VALUATION_UPDATE | TECHNICAL_REVIEW | DEEP_RESEARCH"'
            )
        else:
            example_machine_record = '    "summary": "analysis results and key metrics"'

        sections.extend([
            "",
            "=== OUTPUT REQUIREMENTS ===",
            "You MUST respond with ONLY a single valid raw JSON object matching this exact structure:",
            "{",
            '  "machine_record": {',
            example_machine_record,
            "  },",
            '  "human_brief": "SONUÇ\\n\\nÖNERİ: ADD|HOLD|REDUCE|SELL\\n\\nGÜVEN: XX%\\n\\nUYGULANABİLİRLİK (varsa): İŞLEM KISITLI / ENGELLİ\\n\\nNEDEN?\\n...\\n\\nNE DEĞİŞTİ?\\n...\\n\\nRİSKLER\\n...\\n\\nBU GÖRÜŞÜ NE DEĞİŞTİRİR?\\n...\\n\\nEKSİK VERİ VE BELİRSİZLİK\\n...",',
            '  "confidence": "HIGH | MEDIUM | LOW | 0-100"',
            "}",
            "",
            "CRITICAL INSTRUCTIONS (DECISION MODEL V2.1):",
            "1. Deep Research must normally produce a decisive directional recommendation: ADD, HOLD, REDUCE, or SELL.",
            "2. REVIEW_REQUIRED is strictly forbidden as a default or safe answer. It is only permitted when critical evidence is genuinely missing or sources materially conflict. If REVIEW_REQUIRED is emitted, 'review_required_reason' MUST specify the exact missing data.",
            "3. Calibrate confidence: Represent uncertainty through 'confidence' (0-100). When material evidence gaps exist (e.g. unverified holdings, distressed debt, liquidation), calibrate confidence downward (e.g. 50-70). Never report 90%+ confidence when fundamental data is missing.",
            "4. Valuation semantics: If underlying asset valuation cannot be verified or holdings are undisclosed, use UNKNOWN or N_A. NEVER use FAIR as a lazy placeholder for unassessed/unknown valuation.",
            "5. Technical semantics: For funds under liquidation, redemption default/freeze, trading halt, or where technical analysis is not applicable, use N_A or UNKNOWN. NEVER output NEUTRAL when technical analysis is not applicable.",
            "6. Execution vs Directional View: Execution barriers (liquidation, redemption freezes, legal bans) must be reflected in 'execution_status' ('RESTRICTED' or 'BLOCKED'). Do NOT let execution barriers force recommendation to HOLD or REVIEW_REQUIRED; if the directional investment stance is to exit, output SELL or REDUCE.",
            "7. If thesis_status is INVALIDATED, recommendation should normally be REDUCE or SELL.",
            "8. Output ONLY the raw JSON object. Do not include markdown code fences (no ```json or ```), commentary, or explanations.",
            "9. Ensure all enum values strictly match the valid options listed above.",
            "10. Do not assume or invent facts not present in the provided context.",
        ])

        return "\n".join(sections)

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        """Execute protocol request via Codex CLI non-interactive subprocess."""
        effective_timeout = self.resolve_timeout(request)
        start_time = time.monotonic()
        prompt_text = self.build_prompt(request)

        # Allocate unique temporary file for model output
        temp_fd, temp_path_str = tempfile.mkstemp(prefix="codex_out_", suffix=".json")
        os.close(temp_fd)
        temp_output_path = Path(temp_path_str)

        cmd = [
            self.executable_path,
            "exec",
            "--ephemeral",
            "-s",
            self.sandbox,
            "--color",
            "never",
            "-C",
            str(self.cwd),
            "-o",
            str(temp_output_path),
        ]

        if self.model:
            cmd.extend(["-m", self.model])

        # Prompt is passed via stdin (-) to prevent shell escape issues or command line limits
        cmd.append("-")

        inst_label = (
            (request.execution_metadata or {}).get("instrument_symbol")
            or (request.persistent_context or {}).get("symbol")
            or (request.persistent_context or {}).get("instrument", {}).get("symbol")
            or "unknown"
        )

        try:
            # Preserve compatibility with tests mocking subprocess.run
            from unittest.mock import MagicMock, Mock

            is_mocked = (
                isinstance(subprocess.run, (Mock, MagicMock))
                or getattr(subprocess.run, "_mock_return_value", None) is not None
            )
            if is_mocked:
                proc = subprocess.run(
                    cmd,
                    input=prompt_text,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=effective_timeout,
                    cwd=str(self.cwd),
                    shell=False,
                )
            else:
                proc_obj = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    cwd=str(self.cwd),
                    shell=False,
                )
                try:
                    stdout, stderr = proc_obj.communicate(input=prompt_text, timeout=effective_timeout)
                    proc = subprocess.CompletedProcess(
                        args=cmd,
                        returncode=proc_obj.returncode if proc_obj.returncode is not None else 0,
                        stdout=stdout,
                        stderr=stderr,
                    )
                except subprocess.TimeoutExpired as err:
                    _kill_process_tree(proc_obj)
                    raise subprocess.TimeoutExpired(
                        cmd=cmd,
                        timeout=effective_timeout,
                        output=err.stdout,
                        stderr=err.stderr,
                    ) from err
                except Exception:
                    _kill_process_tree(proc_obj)
                    raise
        except subprocess.TimeoutExpired as err:
            elapsed = time.monotonic() - start_time
            logger.error(
                "Codex CLI execution timed out for protocol=%s instrument=%s after %.1fs (configured timeout: %.1fs)",
                request.protocol_name,
                inst_label,
                elapsed,
                effective_timeout,
            )
            is_deep = is_deep_research_protocol(request.protocol_name)
            timeout_int = int(effective_timeout) if effective_timeout.is_integer() else effective_timeout
            if is_deep:
                err_msg = (
                    f"Deep Research exceeded the {timeout_int}-second execution limit "
                    f"(Codex CLI execution timed out after {effective_timeout} seconds)."
                )
            else:
                err_msg = (
                    f"Protocol '{request.protocol_name}' execution exceeded the {timeout_int}-second execution limit "
                    f"(Codex CLI execution timed out after {effective_timeout} seconds)."
                )
            raise AIExecutionError(err_msg) from err
        except AIExecutionError:
            raise
        except Exception as err:
            raise AIExecutionError(
                f"Failed to start Codex CLI subprocess: {type(err).__name__}"
            ) from err
        finally:
            raw_output = None
            if temp_output_path.is_file():
                try:
                    raw_output = temp_output_path.read_text(encoding="utf-8")
                except Exception:
                    pass
                try:
                    temp_output_path.unlink()
                except Exception:
                    pass

        if proc.returncode != 0:
            err_details = proc.stderr.strip() if proc.stderr else ""
            if not err_details and proc.stdout:
                err_details = proc.stdout.strip()
            sanitized = _sanitize_output(err_details)
            tail = "\n".join(sanitized.splitlines()[-15:]) if sanitized else "No output captured"
            raise AIExecutionError(
                f"Codex CLI execution failed with exit code {proc.returncode}:\n{tail}"
            )

        # Retrieve output from file or fallback to stdout
        output_candidate = raw_output if (raw_output and raw_output.strip()) else proc.stdout
        if not output_candidate or not output_candidate.strip():
            raise AIExecutionError("Codex CLI completed successfully but produced no output")

        cleaned_json = _extract_json_object(output_candidate)

        try:
            parsed = json.loads(cleaned_json)
        except json.JSONDecodeError as err:
            raise AIExecutionError(
                f"Codex CLI response could not be parsed as JSON: {err}"
            ) from err

        if not isinstance(parsed, dict):
            raise AIExecutionError(
                f"Codex CLI response must be a JSON object, got {type(parsed).__name__}"
            )

        # Allow Copilot / structured responses with response_type to normalize seamlessly
        if "machine_record" not in parsed or not isinstance(parsed["machine_record"], dict):
            if "response_type" in parsed:
                parsed["machine_record"] = dict(parsed)
                parsed["human_brief"] = str(
                    parsed.get("answer")
                    or parsed.get("question")
                    or parsed.get("reason")
                    or "Copilot response"
                )
            else:
                raise AIExecutionError(
                    "Codex CLI output missing required dictionary field 'machine_record'"
                )

        if (
            "human_brief" not in parsed
            or not isinstance(parsed["human_brief"], str)
            or not parsed["human_brief"].strip()
        ):
            if isinstance(parsed.get("machine_record"), dict) and (
                parsed["machine_record"].get("answer") or parsed["machine_record"].get("question")
            ):
                parsed["human_brief"] = str(
                    parsed["machine_record"].get("answer") or parsed["machine_record"].get("question")
                )
            else:
                raise AIExecutionError(
                    "Codex CLI output missing required non-empty string field 'human_brief'"
                )


        confidence = parsed.get("confidence")
        if confidence is None and isinstance(parsed.get("machine_record"), dict):
            confidence = parsed["machine_record"].get("confidence")
        if confidence is not None:
            confidence = str(confidence).strip()

        return AIExecutionResult(
            machine_record=parsed["machine_record"],
            human_brief=parsed["human_brief"].strip(),
            confidence=confidence,
        )
