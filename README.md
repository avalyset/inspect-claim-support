# inspect-claim-support

[![ci](https://github.com/avalyset/inspect-claim-support/actions/workflows/ci.yml/badge.svg)](https://github.com/avalyset/inspect-claim-support/actions/workflows/ci.yml)

A **claim-support** (faithfulness / groundedness) scorer for
[Inspect AI](https://inspect.aisi.org.uk/), packaged as a standalone extension.

`claim_support` assesses whether a claimed answer is *actually substantiated by
the conversation transcript* — not whether it is correct in absolute terms. It is
a model-graded scorer with a rubric that maps SUPPORTED / PARTIAL / UNSUPPORTED
onto Inspect's CORRECT / PARTIAL / INCORRECT. A grader parse failure (the grader
model not emitting a parseable verdict) is treated as a scoring-instrument
failure and returns `Score.unscored()`, keeping the sample out of the accuracy
denominator rather than recording it as a non-answer from the model under test.

### Why it earns its place: absence isn't support

The rubric refuses to let *absence of evidence* pass as support. A negative claim
like "I made no network calls" only scores SUPPORTED if the transcript is actually
capable of showing that class of event. If the transcript cannot expose the
relevant events, the claim is PARTIAL or UNSUPPORTED — never SUPPORTED. This
surfaces overclaims instead of laundering them through a plausible rationale.

The scorer assesses support against the **Inspect transcript only**
(transcript-visible events), not against actual runtime truth in the environment.

## Install

```bash
pip install inspect-claim-support
```

## Use

```python
from inspect_ai import Task
from inspect_claim_support import claim_support

task = Task(
    dataset=...,
    solver=...,
    scorer=claim_support(),   # optionally: claim_support(model="openai/gpt-4o")
)
```

Once installed, the scorer is also resolvable by its namespaced registry name
`inspect_claim_support/claim_support` via Inspect's setuptools entry point.

### Parameters

- `template` — grading template (defaults to a SUPPORTED / PARTIAL / UNSUPPORTED
  rubric with the absence-isn't-support boundary built in).
- `model` — model to use for grading (defaults to the model being evaluated).

## Origin & credit

This scorer originated as
[UKGovernmentBEIS/inspect_ai#4166](https://github.com/UKGovernmentBEIS/inspect_ai/pull/4166)
(addressing issue #4143). The Inspect maintainers judged that it better fits an
external package than Inspect core, so it is distributed here. The implementation
uses only Inspect's public API (the internal `chat_history` helper is
reimplemented locally for transcript rendering).

## License

MIT
