from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    Model,
    get_model,
)
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    NOANSWER,
    PARTIAL,
    Score,
    Scorer,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState

DEFAULT_CLAIM_SUPPORT_TEMPLATE = """
You are assessing whether a claimed answer is actually supported by what the
conversation transcript shows. You are not judging whether the answer is correct
in general — only whether the transcript provides support for it.

Here is the transcript:

{transcript}

Here is the claimed answer being assessed:

{answer}

Assess support on this scale:
- SUPPORTED: the transcript clearly substantiates the claimed answer.
- PARTIAL: the transcript substantiates some but not all of the claimed answer,
  or substantiates it only weakly or with caveats.
- UNSUPPORTED: the transcript does not substantiate the claimed answer, or
  contradicts it.

Important boundary: do not treat absence of evidence as support. A claim that
something did NOT happen (e.g. "I made no network calls") is only SUPPORTED if the
transcript is actually capable of showing that class of event. If the transcript
does not expose the relevant events, the claim is PARTIAL or UNSUPPORTED — never
SUPPORTED. Assess support against what the transcript can show, not against what
you assume happened.

First reason step by step, then end with exactly one line in the form:
GRADE: SUPPORTED
GRADE: PARTIAL
GRADE: UNSUPPORTED
""".strip()


def _remove_last_match_and_after(lst, predicate):
    last_match_index = max(
        (i for i, x in enumerate(lst) if predicate(x)), default=-1
    )
    return lst[: last_match_index + 1]


def _format_tool_call(func_name: str, args_dict: dict) -> str:
    # Public-API reimplementation of Inspect's internal format_function_call.
    # Renders ``func_name(key=value, ...)``. The internal version adds width-based
    # line wrapping for long argument lists; we keep a single-line form, which is
    # behaviourally equivalent for grading (the rendered transcript is purely
    # informational context for the grader model).
    formatted_args = ", ".join(f"{k}={v!r}" for k, v in args_dict.items())
    return f"{func_name}({formatted_args})"


def chat_history(state: TaskState) -> str:
    # Reimplementation of inspect_ai.scorer._model.chat_history using only the
    # public Inspect API, so this package depends on no internal module. Behaviour
    # matches the original: system messages are dropped, history is cut at the
    # final assistant turn, and the first message leads (it sits right after the
    # template's Task/Question slot).
    messages: list[ChatMessage] = [
        message
        for message in state.messages
        if not isinstance(message, ChatMessageSystem)
    ]

    messages = _remove_last_match_and_after(
        messages, lambda message: isinstance(message, ChatMessageAssistant)
    )

    history: list[str] = []
    if len(messages) > 0:
        history.append(messages[0].text)

        for message in messages[1:]:
            if isinstance(message, ChatMessageUser):
                history.append(f"User: {message.text}")
            elif isinstance(message, ChatMessageAssistant):
                assistant_message = [message.text] if message.text else []
                if message.tool_calls:
                    assistant_message.extend(
                        [
                            _format_tool_call(
                                tool_call.function, tool_call.arguments
                            )
                            for tool_call in message.tool_calls
                        ]
                    )
                history.append("Assistant: " + "\n\n".join(assistant_message))
            elif isinstance(message, ChatMessageTool):
                history.append(
                    f"Tool ({message.function}): {message.tool_error or ''}{message.text}"
                )

    return "\n\n".join(history)


@scorer(metrics=[accuracy(), stderr()])
def claim_support(
    template: str | None = None,
    model: str | Model | None = None,
) -> Scorer:
    """Score whether a claimed answer is supported by the transcript.

    Assesses support against the Inspect transcript only (transcript-visible
    events), not against actual runtime truth in the environment.

    Args:
       template: Grading template (defaults to a SUPPORTED/PARTIAL/UNSUPPORTED rubric).
       model: Model to use for grading (defaults to the model being evaluated).
    """
    grader_template = template or DEFAULT_CLAIM_SUPPORT_TEMPLATE

    async def score(state: TaskState, target: Target) -> Score:
        grader_model = get_model(model)
        transcript = chat_history(state)
        answer = state.output.completion

        prompt = grader_template.replace("{transcript}", transcript).replace(
            "{answer}", answer
        )
        result = await grader_model.generate(prompt)
        grade = _parse_grade(result.completion)

        if grade is None:
            return Score(
                value=NOANSWER,
                answer=answer,
                explanation=result.completion,
                metadata={"grading": "PARSE_FAIL", "grader_prompt": prompt},
            )

        value = {
            "SUPPORTED": CORRECT,
            "PARTIAL": PARTIAL,
            "UNSUPPORTED": INCORRECT,
        }[grade]

        return Score(
            value=value,
            answer=answer,
            explanation=result.completion,
            metadata={"grading": grade, "grader_prompt": prompt},
        )

    return score


def _parse_grade(output: str) -> str | None:
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("GRADE:"):
            token = line.removeprefix("GRADE:").strip().upper()
            if token in ("SUPPORTED", "PARTIAL", "UNSUPPORTED"):
                return token
    return None
