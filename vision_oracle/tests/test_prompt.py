"""
Unit tests for PromptBuilder and VerdictParser.
Verifies multimodal prompt formatting, markdown JSON extraction, grammar validation, and graceful fallback.
"""

import pytest
from local_vision_oracle.schemas import DefectType, Verdict
from local_vision_oracle.pruner import PrunedNode
from local_vision_oracle.prompt import PromptBuilder, VerdictParser, ORACLE_SYSTEM_PROMPT


def test_prompt_builder_formats_pruned_nodes():
    builder = PromptBuilder()
    nodes = [
        PrunedNode(
            element_id="com.app:id/title",
            class_name="android.widget.TextView",
            text="Cart Items",
            content_desc="",
            bounds=[50, 40, 100, 400],
            clickable=False,
            scrollable=False,
        ),
        PrunedNode(
            element_id="com.app:id/btn_buy",
            class_name="android.widget.Button",
            text="Buy Now",
            content_desc="",
            bounds=[850, 100, 930, 900],
            clickable=True,
            scrollable=False,
        ),
    ]

    prompt = builder.build_user_prompt(nodes, metadata={"activity": "CheckoutActivity"})
    assert "CheckoutActivity" in prompt
    assert '<TextView id="title" text="Cart Items" bounds=[50, 40, 100, 400]' in prompt
    assert '<Button id="btn_buy" text="Buy Now" bounds=[850, 100, 930, 900] clickable' in prompt


def test_prompt_builder_vision_only():
    builder = PromptBuilder()
    prompt = builder.build_user_prompt(pruned_nodes=None)
    assert "visual cues only" in prompt


def test_qwen_chat_input_structure():
    builder = PromptBuilder()
    messages = builder.build_qwen_chat_input(image_content="fake_img_obj", pruned_nodes=[])
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == ORACLE_SYSTEM_PROMPT
    assert messages[1]["role"] == "user"
    assert messages[1]["content"][0]["type"] == "image"
    assert messages[1]["content"][1]["type"] == "text"


def test_verdict_parser_clean_json():
    raw_json = """
    {
      "has_defect": false,
      "defect_type": "none",
      "confidence": 0.98,
      "bounding_box": null,
      "affected_element_id": null,
      "explanation": "No rendering or functional defects observed."
    }
    """
    verdict = VerdictParser.parse(raw_json)
    assert isinstance(verdict, Verdict)
    assert verdict.has_defect is False
    assert verdict.defect_type == DefectType.NONE
    assert verdict.confidence == 0.98
    assert verdict.bounding_box is None


def test_verdict_parser_markdown_fenced():
    raw_response = """Here is my analysis of the screen:
    ```json
    {
      "has_defect": true,
      "defect_type": "component_overlap",
      "confidence": 0.94,
      "bounding_box": [800, 100, 900, 900],
      "affected_element_id": "com.app:id/btn_buy",
      "explanation": "Buy button visually occludes total price text."
    }
    ```
    I hope this helps!
    """
    verdict = VerdictParser.parse(raw_response)
    assert verdict.has_defect is True
    assert verdict.defect_type == DefectType.COMPONENT_OVERLAP
    assert verdict.confidence == 0.94
    assert verdict.bounding_box == [800, 100, 900, 900]
    assert verdict.affected_element_id == "com.app:id/btn_buy"


def test_verdict_parser_unrecognized_defect_type():
    raw_json = """
    {
      "has_defect": true,
      "defect_type": "some_novel_contrast_issue",
      "confidence": 0.85,
      "bounding_box": [100, 100, 200, 200],
      "explanation": "Contrast too low."
    }
    """
    verdict = VerdictParser.parse(raw_json)
    assert verdict.has_defect is True
    assert verdict.defect_type == DefectType.OTHER
    assert verdict.sub_category == "some_novel_contrast_issue"


def test_verdict_parser_graceful_fallback_on_corrupt():
    corrupt_text = "I cannot parse this screen because of server error."
    verdict = VerdictParser.parse(corrupt_text)
    assert verdict.has_defect is False
    assert verdict.confidence == 0.0
    assert "Malformed" in verdict.explanation
