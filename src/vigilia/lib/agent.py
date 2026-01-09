from dataclasses import dataclass
from textwrap import dedent

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from ..conf import DEFAULT_RETRIES


@dataclass
class FragmentSummarisationDeps:
    patch_fragment: str
    tree: str | None = None


@dataclass
class SummaryConsolidationDeps:
    partial_summaries: list[str]
    tree: str | None = None


_SHARED_SYSTEM_PROMPT = dedent("""\
    You are a technical writer that specialises in writing clear,
    concise and comprehensive technical summaries of code changes for software
    engineering teams.

    Your task is to produce a well-structured documentation that describe technical
    changes in a way that is easy to understand for other engineers familiar
    with the codebase.

    Here are some guidelines on formatting and style:

    - Use accessible language
    - Be concise but complete!
    - Include a title, a short introduction and the description of changes
    - Focus on the most significant changes, such as structural refactors,
      changes in architecture, or infrastructure. Ignore small details that
      won't affect the review, or ones that will be clearly noticed from
      the code-changes alone and need no further commentary.
    - Group changes in sections, if the changes are unrelated, use sub-headings
      for section titles, for example, separated by concerns: backend, frontend,
      infrastructure, CI, etc.
    - Use lists in sections to separate each set of changes individually, but
      keep the formatting simple, don't add subheadings to each list item or use
      too much bold or italics
    - Include code-samples rather than explanations when it makes more sense.
    - Rank sections from most important to least
    - The length of the description should be proportional to the changes,
      i.e. a major refactor needs a bigger explanation, a change to a few files
      requires less.
    - Do not include language value judgements on any of the changes, do not use
      words such as "significant" or "comprehensive"
    - Do not assess the efficacy of the changes
    - Do not try and interpret the reasoning behind the changes
    - Format the output in a markdown!
    """)


def get_fragment_summarisation_agent(
    model: Model | str,
) -> Agent[FragmentSummarisationDeps]:
    """
    Configure a pydantic-ai Agent for summarising a single code diff fragment.

    Accepts either a model instance or a model identifier string.

    Example:
        >>> agent = get_fragment_summarisation_agent("anthropic:claude-opus-4-5")
        >>> result = agent.run_sync(
        ...     "Go!",
        ...     deps=FragmentSummarisationDeps(patch_fragment="diff content here")
        ... )
        >>> print(result.output)

        >>> from pydantic_ai.models.test import TestModel
        >>> agent = get_fragment_summarisation_agent(TestModel())
    """
    agent = Agent(
        model=model, deps_type=FragmentSummarisationDeps, retries=DEFAULT_RETRIES
    )

    @agent.system_prompt
    def system_prompt(ctx: RunContext[FragmentSummarisationDeps]) -> str:
        return _SHARED_SYSTEM_PROMPT

    @agent.instructions
    def instructions(ctx: RunContext[FragmentSummarisationDeps]) -> str:
        parts = [
            dedent("""\
                Write a comprehensive technical document summarising the code-changes.

                The audience is other engineers that are familiar with this code - the
                summary should point them to the aspects of these changes that they will
                need to consider in the future and remind them of the changes that the codebase
                has undergone.
                """)
        ]

        if ctx.deps.tree:
            parts.append("Here the tree structure of the overall changes:\n\n")
            parts.append(ctx.deps.tree)

        parts.append("\n\nHere is the fragment of code changes to summarise:\n\n")
        parts.append(ctx.deps.patch_fragment)

        return "".join(parts)

    return agent


def get_summary_consolidation_agent(
    model: Model | str,
) -> Agent[SummaryConsolidationDeps]:
    """
    Configure a pydantic-ai Agent for merging multiple fragment summaries.

    Accepts either a model instance or a model identifier string.

    Example:
        >>> agent = get_summary_consolidation_agent("anthropic:claude-opus-4-5")
        >>> result = agent.run_sync(
        ...     "Go!",
        ...     deps=SummaryConsolidationDeps(partial_summaries=["summary 1", "summary 2"])
        ... )
        >>> print(result.output)

        >>> from pydantic_ai.models.test import TestModel
        >>> agent = get_summary_consolidation_agent(TestModel())
    """
    agent = Agent(
        model=model, deps_type=SummaryConsolidationDeps, retries=DEFAULT_RETRIES
    )

    @agent.system_prompt
    def system_prompt(ctx: RunContext[SummaryConsolidationDeps]) -> str:
        return _SHARED_SYSTEM_PROMPT

    @agent.instructions
    def instructions(ctx: RunContext[SummaryConsolidationDeps]) -> str:
        parts = [
            dedent("""\
                You are given several partial summaries of code changes over a period of time.
                Your task is to produce a single, unified summary that:

                - Consolidates overlapping information — where multiple summaries cover the
                  same point, state it once with appropriate weight
                - Preserves unique insights — if only one summary mentions something
                  substantive, include it
                - Resolves contradictions — if summaries conflict, note the disagreement
                  briefly or use your judgement to determine which is more likely correct
                - Maintains appropriate granularity — the output should be shorter than the
                  combined input, but detailed enough to capture the key substance
                - Combine these fragment summaries into a single coherent document.

                Maintain the format and style, but merge related sections and eliminate redundancy.
                """)
        ]

        if ctx.deps.tree:
            parts.append("\n\nHere the tree structure of the overall changes:\n\n")
            parts.append(ctx.deps.tree)

        parts.append("\n\nHere is a list of partial summaries:\n\n")
        parts.append(
            "\n\n".join(
                f"## Partial Summary {i}:\n-------------------\n\n{summary}"
                for i, summary in enumerate(ctx.deps.partial_summaries)
            )
        )

        return "".join(parts)

    return agent
