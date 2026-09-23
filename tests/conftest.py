from __future__ import annotations

import json


class StructuredModel:
    def __init__(self, responses):
        self.responses = responses
        self.inputs = []
        self.schema = None

    def with_structured_output(self, schema, *, strict):
        assert strict
        self.schema = schema
        return self

    def invoke(self, messages):
        self.inputs.append(json.loads(messages[0].content))
        return self.responses[self.schema].pop(0)
