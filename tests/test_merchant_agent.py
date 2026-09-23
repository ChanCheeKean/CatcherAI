from __future__ import annotations

from pathlib import Path

import pytest
from conftest import StructuredModel
from submissions import load_saved

from extensions.merchant_agent.agent import record_tools, respond
from extensions.merchant_agent.contract import (
    EvidenceAsk,
    MerchantEvidenceRequest,
    MerchantSubmission,
    SubmittedItem,
)
from extensions.merchant_agent.store import save_submission


def test_respond_and_save_round_trip(tmp_path):
    request = MerchantEvidenceRequest(
        dispute_id="DSP-2026-91001",
        merchant_id="MER-HGF",
        charge_ids=["CHG-A01"],
        asks=[EvidenceAsk(topic="accepted terms", detail="Show the checkout acceptance")],
    )
    submission = MerchantSubmission(
        submission_id="MSB-A01-TEST",
        dispute_id=request.dispute_id,
        merchant_id=request.merchant_id,
        statement="The checkout terms were accepted.",
        items=[SubmittedItem(kind="acceptance_log", text="ORD-A01 accepted", asserts=["ORD-A01"])],
        messages=[],
        cited_ids=["CLS-HGF-CO-V4-4.3"],
    )
    fake_model = StructuredModel({MerchantSubmission: [submission]})
    built = {}

    class Agent:
        def invoke(self, messages):
            return {"structured_response": fake_model.invoke(messages)}

    def builder(**kwargs):
        built.update(kwargs)
        fake_model.with_structured_output(MerchantSubmission, strict=True)
        return Agent()

    assert respond(request, Path("data/merchant_records"), fake_model, builder) == submission
    assert fake_model.inputs == [request.model_dump()]
    assert {tool.name for tool in built["tools"]} == {"list_records", "read_record"}
    path = save_submission(submission, tmp_path)
    assert path == tmp_path / "DSP-2026-91001.json"
    assert load_saved(tmp_path) == [submission]


def test_record_tools_are_read_only_and_confined(tmp_path):
    merchant = tmp_path / "MER-HGF"
    merchant.mkdir()
    (merchant / "orders.json").write_text('{"id":"ORD-A01"}')
    (merchant / "large.txt").write_text("x" * 15_000)
    (tmp_path / "secret.txt").write_text("private")
    (merchant / "escape.txt").symlink_to(tmp_path / "secret.txt")
    tools = {tool.name: tool for tool in record_tools(merchant)}
    assert "orders.json" in tools["list_records"].invoke({})
    assert "ORD-A01" in tools["read_record"].invoke({"name": "orders.json"})
    assert len(tools["read_record"].invoke({"name": "large.txt"})) == 12_000
    assert "error" in tools["read_record"].invoke({"name": "../../etc/passwd"}).lower()
    assert "error" in tools["read_record"].invoke({"name": "escape.txt"}).lower()


def test_respond_rejects_merchant_directory_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "records"
    root.mkdir()
    (root / "MER-HGF").symlink_to(outside)
    request = MerchantEvidenceRequest(
        dispute_id="DSP-1", merchant_id="MER-HGF", charge_ids=[], asks=[]
    )
    with pytest.raises(ValueError, match="outside the records root"):
        respond(request, root, object(), lambda **_: None)


def test_extension_is_not_wired_into_runtime():
    for path in Path("src").rglob("*.py"):
        if Path("src/extensions") in path.parents:
            continue
        assert "extensions" not in path.read_text(), path
    for path in Path("config").glob("*.yaml"):
        assert "merchant_agent" not in path.read_text(), path
