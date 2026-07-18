"""Explicit agent capabilities; multi-agent is a permission model, not prompt splitting."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from t3c2_path.domain import FrozenModel


class AgentCapability(StrEnum):
    READ_EVIDENCE = "READ_EVIDENCE"
    READ_RULE = "READ_RULE"
    WRITE_PROFILE = "WRITE_PROFILE"
    WRITE_PATH = "WRITE_PATH"
    WRITE_TASK = "WRITE_TASK"
    WRITE_GATE = "WRITE_GATE"
    WRITE_EXPLANATION = "WRITE_EXPLANATION"
    WRITE_AUDIT = "WRITE_AUDIT"


class AgentPermissionError(PermissionError):
    """Raised when an agent attempts an undeclared state transition."""


class AgentContract(FrozenModel):
    agent_name: str = Field(min_length=1)
    capabilities: frozenset[AgentCapability] = Field(min_length=1)

    def require(self, capability: AgentCapability) -> None:
        if capability not in self.capabilities:
            raise AgentPermissionError(
                f"{self.agent_name} does not have capability {capability.value}"
            )

    @classmethod
    def evidence_agent(cls) -> AgentContract:
        return cls(
            agent_name="evidence-agent",
            capabilities=frozenset(
                {AgentCapability.READ_EVIDENCE, AgentCapability.WRITE_PROFILE}
            ),
        )

    @classmethod
    def path_agent(cls) -> AgentContract:
        return cls(
            agent_name="path-agent",
            capabilities=frozenset({AgentCapability.READ_RULE, AgentCapability.WRITE_PATH}),
        )

    @classmethod
    def task_agent(cls) -> AgentContract:
        return cls(
            agent_name="task-agent",
            capabilities=frozenset({AgentCapability.READ_RULE, AgentCapability.WRITE_TASK}),
        )

    @classmethod
    def governance_agent(cls) -> AgentContract:
        return cls(
            agent_name="governance-agent",
            capabilities=frozenset({AgentCapability.READ_RULE, AgentCapability.WRITE_GATE}),
        )

    @classmethod
    def explanation_agent(cls) -> AgentContract:
        return cls(
            agent_name="explanation-agent",
            capabilities=frozenset({AgentCapability.WRITE_EXPLANATION}),
        )

    @classmethod
    def audit_agent(cls) -> AgentContract:
        return cls(
            agent_name="audit-agent",
            capabilities=frozenset({AgentCapability.WRITE_AUDIT}),
        )


__all__ = ["AgentCapability", "AgentContract", "AgentPermissionError"]
