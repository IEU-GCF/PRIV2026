# Model Specification

## Model

- **Deployment:** `gpt-5.4-mini`, served on GCF IEU's own Azure AI Foundry endpoint
  (`https://gcf-ieu-foundry.services.ai.azure.com/openai/v1`), not the public OpenAI API.
- **Auth:** Microsoft Entra ID via `InteractiveBrowserCredential` -- a one-time browser
  sign-in per run, no API keys stored anywhere in the repo. Requires the GCF office
  network or GCF VPN.
- **API surface:** the OpenAI-compatible Responses API (`client.responses.create()`),
  not the older Chat Completions API.

## Call parameters

| Parameter | Value | Why |
|---|---|---|
| `temperature` | `0.0` | As close to deterministic/repeatable as this model allows. Some reasoning-tuned deployments reject a custom temperature outright (HTTP 400); the client detects that and falls back to the deployment's default rather than failing the run. |
| `reasoning.effort` | `"low"` | `gpt-5.4-mini` is a reasoning model -- it spends an invisible, variable number of tokens "thinking" before writing the visible JSON, and those tokens count against the output cap too. "Low" keeps that invisible spend small for a task this structured (decision tables + worked examples already do most of the work), leaving more of the budget for the actual answer, and costs less. Same fallback pattern as temperature if a deployment rejects it. |
| `max_output_tokens` | `20,000` | Cost is based on tokens actually used, not this ceiling, so a generous cap is close to free -- it only guards against premature cutoff. Raised twice during the pilot (1,200 -> 8,000 -> 14,000 -> 20,000) after real truncated-JSON failures at each lower value; see Reliability below. |
| Output format | A single JSON object per call, enforced entirely through prompt instructions (schema + "return exactly this JSON object, nothing else, no markdown fences") -- not a structured-output / JSON-mode API parameter. |

## Reliability: truncated replies

At scale (a 266-proposal batch, 2026-08), roughly 27% of calls initially came back
as malformed JSON, always a reply cut off mid-string. None of these ever set the
Responses API's `status == "incomplete"` flag the client was checking for, so this
Foundry deployment does not reliably surface that signal -- a cut-off reply just
looks like a generic JSON parse failure after the fact, with no way to tell truncation
apart from a genuinely malformed reply.

Two changes address this in `src/foundry_client.py`:

1. `max_output_tokens` raised to 20,000 (real headroom, see table above).
2. `ask_json()` retries automatically (up to 2 extra attempts) on a JSON parse failure
   before raising an error, since a truncated reply is usually a one-off, the same
   call very often succeeds on retry. This alone resolved 76 of 77 failures in the
   266-proposal batch; the one that didn't got flagged for manual follow-up rather
   than silently producing a wrong answer.

## Determinism

`temperature=0.0` and `reasoning.effort="low"` are configured for maximum
repeatability, but this is **not** a guarantee of byte-identical output between runs.
Two runs of the same prompt can reasonably differ in exact wording, or in which
subset of several valid entities a synthesis call chooses to surface, even when the
underlying evidence and verdict are the same. Every criterion result still traces
back to a verbatim quote from the source document (see "Quote-grounding" in the
main README), so this is an auditability guarantee, not a reproducibility one:
re-running won't necessarily produce identical text, but every claim in whatever
text it does produce is checkable against the proposal.

## Cost control

- `run_pilot.py` and `synthesize_summary.py` are both re-run-safe: re-running with
  the same inputs skips any row that already scored successfully, and only sends a
  fresh call for rows that are new, or that previously errored. Nothing gets
  re-paid for by accident.
- `--criteria` lets you re-score a single criterion across every proposal (e.g.
  after editing one prompt file) without re-paying for the other two.
