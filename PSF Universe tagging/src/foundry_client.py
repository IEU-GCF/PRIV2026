"""
Reusable client for the GCF IEU Azure AI Foundry endpoint (GPT-5.5).

This is the same auth pattern already proven to work elsewhere in the
workspace's `foundry_client.py`: a one-time interactive browser sign-in
(Microsoft Entra ID), no API keys, no `az login` needed. You must be on
the GCF office network or GCF VPN for the call to succeed.

Usage:
    from foundry_client import ask_json
    result = ask_json(system="...", user="...")   # returns a parsed dict
"""

import json

from openai import APIStatusError, APIConnectionError
from azure.identity import (
    InteractiveBrowserCredential,
    get_bearer_token_provider,
    CredentialUnavailableError,
)
from openai import OpenAI

ENDPOINT = "https://gcf-ieu-foundry.services.ai.azure.com/openai/v1"
DEPLOYMENT = "gpt-5.4-mini"  # confirm exact deployment name in the Foundry portal if this errors

# Near-zero so classification is as deterministic/repeatable as this model
# allows. Some reasoning-tuned models reject any temperature other than
# their default and return a 400 -- ask_json() detects that and retries
# without the parameter rather than failing the whole pilot over it.
DEFAULT_TEMPERATURE = 0.0

# gpt-5.4-mini is a reasoning model: it spends an invisible, variable
# number of tokens "thinking" before writing the visible JSON, and those
# reasoning tokens count against max_output_tokens too. "low" keeps that
# invisible spend small for a task this structured (decision tables +
# worked examples already do most of the work), leaving more of the
# budget for the actual answer -- and costs less. Same fallback pattern
# as temperature if this deployment rejects the parameter outright.
DEFAULT_REASONING_EFFORT = "low"

# Confirmed truncating real replies mid-JSON at 1200, and STILL truncating
# at 4000 on longer answers (2026-08-05 pilot run) even after dropping
# reasoning effort to "low" -- raised again with real headroom. Cost is
# based on tokens actually used, not this cap, so a generous ceiling here
# is close to free; it only guards against premature cutoff.
#
# Even at 8000, the 266-FP B45 batch (2026-08) still hit ~27% truncated-JSON
# failures concentrated in criterion 1 and 2 -- and none of them tripped the
# response.status == "incomplete" branch below, so this Foundry deployment
# doesn't reliably surface that flag; a cut-off reply just looks like a
# generic JSON parse failure. Raised further for headroom, and ask_json()
# now retries automatically on a JSON parse failure (see _MAX_JSON_RETRIES)
# instead of failing the FP outright on what is often a one-off truncation.
DEFAULT_MAX_OUTPUT_TOKENS = 20_000

# A truncated-JSON reply is usually a one-off (the same call often succeeds
# on retry), so retry a couple of times before giving up and recording an
# error -- cheap insurance against losing ~1/4 of criterion calls to this.
_MAX_JSON_RETRIES = 2

# The browser sign-in window opens once per Python process (credential is
# cached at module level), so a pilot run scoring many FPs only prompts once.
_credential = InteractiveBrowserCredential()
_token_provider = get_bearer_token_provider(_credential, "https://ai.azure.com/.default")
_client = OpenAI(base_url=ENDPOINT, api_key=_token_provider)

# Set True the first time this deployment 400s on that parameter, so later
# calls in the same run stop retrying it (and stop re-printing the note).
_temperature_unsupported = False
_reasoning_unsupported = False


class FoundryCallError(RuntimeError):
    """Raised with a plain-language explanation any time the model call fails."""


def _call_model(
    system: str,
    user: str,
    max_output_tokens: int,
    temperature: float | None,
    reasoning_effort: str | None,
):
    kwargs = dict(
        model=DEPLOYMENT,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_output_tokens=max_output_tokens,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature
    if reasoning_effort is not None:
        kwargs["reasoning"] = {"effort": reasoning_effort}
    return _client.responses.create(**kwargs)


def ask_json(
    system: str,
    user: str,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
) -> dict:
    """
    Send one system+user prompt pair, expect the model to reply with a single
    JSON object (our criterion prompts all instruct it to), and return that
    object as a Python dict.

    Raises FoundryCallError with a human-readable message on any failure —
    network/VPN issue, sign-in problem, a reply cut off by the token limit,
    or a reply that isn't valid JSON for some other reason.
    """
    global _temperature_unsupported, _reasoning_unsupported
    effective_temperature = None if _temperature_unsupported else temperature
    effective_reasoning = None if _reasoning_unsupported else reasoning_effort

    last_json_error: json.JSONDecodeError | None = None
    last_text: str = ""
    for json_attempt in range(_MAX_JSON_RETRIES + 1):
        response = None
        for _ in range(3):  # initial attempt + up to 2 parameter fallbacks
            try:
                response = _call_model(system, user, max_output_tokens, effective_temperature, effective_reasoning)
                break
            except CredentialUnavailableError as exc:
                raise FoundryCallError(
                    "Could not sign in with Microsoft Entra ID. A browser window should have "
                    "opened for sign-in — if it didn't, or you closed it, re-run the pilot."
                ) from exc
            except APIConnectionError as exc:
                raise FoundryCallError(
                    "Could not reach the Foundry endpoint. Make sure you are connected to the "
                    "GCF office network or GCF VPN, then try again."
                ) from exc
            except APIStatusError as exc:
                if exc.status_code == 403:
                    raise FoundryCallError(
                        "Foundry rejected the request with a 403 (permission denied). This usually "
                        "means you are off the GCF network/VPN, or your account does not yet have "
                        "access to this Foundry deployment — check with IT/IEU tech support."
                    ) from exc

                message = (exc.message or "").lower()
                if exc.status_code == 400 and effective_temperature is not None and "temperature" in message:
                    print(
                        f"Note: this deployment ({DEPLOYMENT}) doesn't support a custom temperature "
                        "-- continuing with its default for the rest of this run."
                    )
                    _temperature_unsupported = True
                    effective_temperature = None
                    continue
                if exc.status_code == 400 and effective_reasoning is not None and "reasoning" in message:
                    print(
                        f"Note: this deployment ({DEPLOYMENT}) doesn't support setting reasoning effort "
                        "-- continuing with its default for the rest of this run."
                    )
                    _reasoning_unsupported = True
                    effective_reasoning = None
                    continue

                raise FoundryCallError(
                    f"Foundry call failed with HTTP {exc.status_code}: {exc.message}"
                ) from exc
        else:
            raise FoundryCallError("Foundry call failed repeatedly even after removing unsupported parameters.")

        if getattr(response, "status", None) == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", "unknown")
            raise FoundryCallError(
                f"Response was cut off before finishing (incomplete, reason: {reason}) -- "
                f"max_output_tokens={max_output_tokens} was too low for this reply. Raise "
                f"DEFAULT_MAX_OUTPUT_TOKENS in foundry_client.py and retry. Partial reply:\n"
                f"{response.output_text[:500]}"
            )

        last_text = response.output_text
        try:
            return json.loads(last_text)
        except json.JSONDecodeError as exc:
            last_json_error = exc
            if json_attempt < _MAX_JSON_RETRIES:
                print(f"  Note: reply wasn't valid JSON (attempt {json_attempt + 1}/{_MAX_JSON_RETRIES + 1}) -- retrying.")
                continue

    # Kept long (not the old 500-char preview) -- a short preview looks
    # identical for two different root causes (genuine token-cap truncation
    # vs. a malformed/unescaped-quote break earlier in the reply) and there
    # was no way to tell them apart after the fact (FP281, 2026-08).
    raise FoundryCallError(
        "The model did not return valid JSON, even after retrying. Raw reply has been kept for inspection:\n"
        f"{last_text[:4000]}"
    ) from last_json_error
