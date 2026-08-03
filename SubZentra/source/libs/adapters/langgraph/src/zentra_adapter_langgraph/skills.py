"""Named instruction packs, loaded from disk and appended per role.

The Cube Analyst's interpret prompt had grown to twenty lines covering four
unrelated disciplines: how to name a period, how to count a sample, how to
report confidence, how to phrase a summary. Every Agent that needed one of
those had to be given all of them, in prose, copied.

A Skill is one of those disciplines, named, in a file. `applies_to` says which
roles get it, so the Evaluator can inherit sample-size discipline without also
inheriting the Analyst's summary voice.

Loaded from markdown with YAML-ish frontmatter — the same convention the docs
vault uses, so a skill reads like the rest of this repository's prose.
Deliberately not read per call: skills are stable per role, and they are
appended to the *system* prompt, which providers cache. A skill that varied per
investigation would silently break that cache on every request.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from zentra_domain_agent_execution import AgentRole

SKILL_ROOT = Path(__file__).parent / "skills"


class MalformedSkillError(ValueError):
    """A skill file is missing frontmatter or a field it must declare."""


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    applies_to: frozenset[AgentRole]
    instructions: str


def parse_skill(text: str, *, source: str) -> Skill:
    """One skill file: `--- key: value ---` frontmatter, then the body."""
    if not text.startswith("---"):
        raise MalformedSkillError(f"{source} has no frontmatter block")
    _, _, rest = text.partition("---")
    front, separator, body = rest.partition("---")
    if not separator:
        raise MalformedSkillError(f"{source} has an unterminated frontmatter block")

    fields: dict[str, str] = {}
    for line in front.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()

    missing = {"name", "applies_to"} - fields.keys()
    if missing:
        raise MalformedSkillError(
            f"{source} declares no {', '.join(sorted(missing))}"
        )
    instructions = body.strip()
    if not instructions:
        raise MalformedSkillError(f"{source} has no instructions")

    return Skill(
        name=fields["name"],
        applies_to=frozenset(
            AgentRole(role.strip())
            for role in fields["applies_to"].split(",")
            if role.strip()
        ),
        instructions=instructions,
    )


class SkillRegistry:
    """The skills this deployment holds, resolved per role."""

    def __init__(self, skills: Iterable[Skill] = ()) -> None:
        # Sorted by name so the composed prompt is byte-stable across
        # processes. Directory iteration order is not, and an unstable system
        # prompt would miss the provider cache on every call.
        self._skills = tuple(sorted(skills, key=lambda skill: skill.name))

    @classmethod
    def from_directory(cls, root: Path = SKILL_ROOT) -> SkillRegistry:
        if not root.is_dir():
            return cls()
        return cls(
            parse_skill(path.read_text(), source=path.name)
            for path in sorted(root.glob("*.md"))
        )

    def for_role(self, role: AgentRole) -> tuple[Skill, ...]:
        return tuple(skill for skill in self._skills if role in skill.applies_to)

    def apply(self, role: AgentRole, system: str) -> str:
        """The system prompt with this role's skills appended.

        Appended rather than prepended: the role's own prompt says what the
        Agent is, and a skill is a refinement of that. A refinement read
        before the thing it refines is just noise.
        """
        skills = self.for_role(role)
        if not skills:
            return system
        blocks = "\n\n".join(
            f"## {skill.name}\n{skill.instructions}" for skill in skills
        )
        return f"{system}\n\n{blocks}"
