from __future__ import annotations

import pytest
from pydantic import ValidationError

from tools.schemas import validate_tool_input


def test_tool_input_is_validated_and_normalized() -> None:
    value = validate_tool_input(
        "get_case",
        {"case_id": "DSP-1", "as_of": "2026-10-21T13:00:00Z"},
    )
    assert value == {"case_id": "DSP-1", "as_of": "2026-10-21T13:00:00Z"}


def test_tool_input_rejects_unknown_arguments() -> None:
    with pytest.raises(ValidationError):
        validate_tool_input(
            "get_case",
            {
                "case_id": "DSP-1",
                "as_of": "2026-10-21T13:00:00Z",
                "ground_truth_path": "forbidden",
            },
        )
