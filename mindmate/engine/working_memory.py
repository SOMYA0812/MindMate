"""Working memory: the short-term fact store used by the inference engine.

Predicates represent true statements such as ``concern:sadness`` or
``need:grounding``. Attributes represent valued facts such as
``duration = "months"`` or ``sleep_hours = 4.5``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class Fact:
    key: str
    source: str = "user"
    certainty: float = 1.0
    evidence: list[str] = field(default_factory=list)
    cycle: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source": self.source,
            "certainty": round(self.certainty, 2),
            "evidence": list(self.evidence),
            "cycle": self.cycle,
        }


class WorkingMemory:
    """A small, inspectable fact base.

    Parameters
    ----------
    predicates:
        Mapping of fact key to :class:`Fact`. Keys are namespaced, e.g.
        ``concern:anxiety``.
    attributes:
        Mapping of attribute name to value. Values may be strings, numbers,
        booleans or lists (for preferences).
    """

    def __init__(self) -> None:
        self.predicates: dict[str, Fact] = {}
        self.attributes: dict[str, Any] = {}
        self.attribute_sources: dict[str, str] = {}

    # -- predicates ------------------------------------------------------
    def assert_fact(self, key: str, source: str = "inference",
                    evidence: Iterable[str] | None = None, cycle: int = 0,
                    certainty: float = 1.0) -> bool:
        """Add a fact. Returns True only when the fact was not already known."""
        if ":" not in key:
            raise ValueError(f"Facts must be namespaced (namespace:value): {key!r}")
        existing = self.predicates.get(key)
        if existing is not None:
            if evidence:
                for item in evidence:
                    if item not in existing.evidence:
                        existing.evidence.append(item)
            existing.certainty = max(existing.certainty, certainty)
            return False
        self.predicates[key] = Fact(
            key=key,
            source=source,
            certainty=certainty,
            evidence=list(evidence or []),
            cycle=cycle,
        )
        return True

    def has(self, key: str) -> bool:
        return key in self.predicates

    def has_any(self, keys: Iterable[str]) -> bool:
        return any(k in self.predicates for k in keys)

    def has_all(self, keys: Iterable[str]) -> bool:
        return all(k in self.predicates for k in keys)

    def count_prefix(self, prefix: str) -> int:
        return sum(1 for key in self.predicates if key.startswith(prefix))

    def facts_snapshot(self) -> list[str]:
        return sorted(self.predicates)

    # -- attributes ------------------------------------------------------
    def set_attribute(self, key: str, value: Any, source: str = "user") -> None:
        if value is None or value == "":
            return
        self.attributes[key] = value
        self.attribute_sources[key] = source

    def get_attribute(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return {
            "predicates": [f.as_dict() for f in self.predicates.values()],
            "attributes": dict(self.attributes),
            "attribute_sources": dict(self.attribute_sources),
        }

    def derived_facts(self) -> list[str]:
        return sorted(
            key for key, fact in self.predicates.items()
            if fact.source == "inference"
        )

    # -- convenience -----------------------------------------------------
    def seed_concerns(self, concerns: Iterable[str], source: str = "user") -> None:
        for concern in concerns:
            self.assert_fact(f"concern:{concern}", source=source)

    def summary(self) -> str:
        """Short human-readable summary used in explanations and logs."""
        concerns = [
            key.split(":", 1)[1] for key in self.facts_snapshot()
            if key.startswith("concern:")
        ]
        parts = []
        if concerns:
            parts.append("concerns: " + ", ".join(concerns))
        if self.attributes:
            visible = {
                k: v for k, v in self.attributes.items()
                if k in {"duration", "impact", "distress", "sleep_hours", "support", "energy", "time_available"}
            }
            if visible:
                parts.append("context: " + ", ".join(f"{k}={v}" for k, v in visible.items()))
        return " | ".join(parts) if parts else "no facts yet"

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"WorkingMemory({len(self.predicates)} facts, {len(self.attributes)} attributes)"
