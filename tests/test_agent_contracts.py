import pytest

from t3c2_path.agents.contracts import AgentCapability, AgentContract, AgentPermissionError


def test_agent_contract_allows_only_declared_capabilities() -> None:
    contract = AgentContract(
        agent_name="evidence-agent",
        capabilities=frozenset(
            {AgentCapability.READ_EVIDENCE, AgentCapability.WRITE_PROFILE}
        ),
    )
    contract.require(AgentCapability.WRITE_PROFILE)
    with pytest.raises(AgentPermissionError, match="WRITE_PATH"):
        contract.require(AgentCapability.WRITE_PATH)


def test_explanation_agent_cannot_modify_structured_results() -> None:
    contract = AgentContract.explanation_agent()
    assert AgentCapability.WRITE_EXPLANATION in contract.capabilities
    assert AgentCapability.WRITE_PROFILE not in contract.capabilities
    assert AgentCapability.WRITE_PATH not in contract.capabilities
