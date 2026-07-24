from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from tools import TOOLS

# ---------------------------------------------------------------------------
# This is the schema every single model step must satisfy. It is the piece
# that turns the loop into a *constrained* ReAct agent instead of a free-form
# one: the model can only ever be in one of three states, and each state has
# exactly the fields it needs, nothing else.
# ---------------------------------------------------------------------------

ALLOWED_TOOLS = tuple(TOOLS.keys())  # <-- the allow-list, defined in one place


class AgentStep(BaseModel):
    action: Literal["tool_call", "final", "escalate"] = Field(
        ..., description="Exactly one of: tool_call, final, escalate."
    )
    tool_name: Optional[str] = Field(
        None, description="Required when action == 'tool_call'. Must be on the allow-list."
    )
    final_answer: Optional[str] = Field(
        None, description="Required when action == 'final'. The recommendation for the passenger."
    )
    escalate_reason: Optional[str] = Field(
        None, description="Required when action == 'escalate'. Why a human needs to take over."
    )

    @model_validator(mode="after")
    def _check_fields_match_action(self):
        if self.action == "tool_call":
            if not self.tool_name:
                raise ValueError("action is 'tool_call' but 'tool_name' is missing.")
            if self.tool_name not in ALLOWED_TOOLS:
                raise ValueError(
                    f"'{self.tool_name}' is not on the allow-list. "
                    f"Allowed tools: {', '.join(ALLOWED_TOOLS)}."
                )
        elif self.action == "final":
            if not self.final_answer or not self.final_answer.strip():
                raise ValueError("action is 'final' but 'final_answer' is missing or empty.")
        elif self.action == "escalate":
            if not self.escalate_reason or not self.escalate_reason.strip():
                raise ValueError("action is 'escalate' but 'escalate_reason' is missing or empty.")
        return self
