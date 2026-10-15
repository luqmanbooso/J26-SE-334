"""
Single-Turn Fused Multimodal Prompt Constructor & Grammar Parser.
Grounded in METHOD-Prompt-Architecture, Ju et al. (OLLM 2024), and Proposal FR3/FR4.
"""

import re
import json
from typing import List, Optional, Dict, Any, Union
from local_vision_oracle.schemas import DefectType, Verdict
from local_vision_oracle.pruner import PrunedNode


ORACLE_SYSTEM_PROMPT = """You are C3: Localized Multimodal Vision-Semantic Test Oracle for Android applications.
Your task is to analyze the provided mobile UI screenshot and pruned view hierarchy to detect non-crash functional and visual defects.

### Defect Taxonomies:
1. component_overlap: Two or more interactive/textual widgets visually collide or occlude each other.
2. text_truncation: Label text is cut off or clipped by parent container boundaries.
3. missing_component: An expected UI element declared in DOM is completely invisible or renders with zero glass area.
4. unrendered_asset: An image container is visible but displays an empty placeholder or broken image icon.
5. functional_incongruence: Visual state contradicts system state (e.g., infinite spinner on success screen).
6. other_defect: Any visual/functional UI defect not covered above (e.g., severe contrast violation).
7. none: The screen renders cleanly with proper spacing, alignment, and rendering.

### Output Grammar (Strict JSON Only):
You must output a single, valid JSON object strictly matching this schema:
{
  "has_defect": <boolean: true or false>,
  "defect_type": "<one of: none, component_overlap, text_truncation, missing_component, unrendered_asset, functional_incongruence, other_defect>",
  "sub_category": "<optional string or null>",
  "confidence": <float between 0.0 and 1.0>,
  "bounding_box": [<ymin>, <xmin>, <ymax>, <xmax>] or null if has_defect is false,
  "affected_element_id": "<resource-id or null>",
  "explanation": "<concise diagnosis>"
}

### Rules:
- All bounding box coordinates MUST be normalized integers in range [0, 1000] where [0,0] is top-left and [1000,1000] is bottom-right.
- Output ONLY the JSON block. Do not include markdown conversational filler.
"""


class PromptBuilder:
    """
    Constructs single-turn fused multimodal prompts interleaving
    visual tokens with pruned view hierarchy elements.
    """

    def __init__(self, system_prompt: str = ORACLE_SYSTEM_PROMPT):
        self.system_prompt = system_prompt

    def format_pruned_nodes(self, nodes: List[PrunedNode]) -> str:
        """
        Formats pruned nodes into compact XML-like token strings.
        """
        if not nodes:
            return "No view hierarchy provided (evaluating vision-only)."

        lines = ["Pruned View Hierarchy:"]
        for node in nodes:
            lines.append(f"  {node.to_prompt_string()}")
        return "\n".join(lines)

    def build_user_prompt(
        self,
        pruned_nodes: Optional[List[PrunedNode]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Builds the text prompt accompanying the screenshot.
        """
        parts = ["Analyze this mobile screen for non-crash visual and semantic defects."]

        if metadata:
            meta_str = ", ".join(f"{k}: {v}" for k, v in metadata.items())
            parts.append(f"App Context: [{meta_str}]")

        if pruned_nodes:
            parts.append(self.format_pruned_nodes(pruned_nodes))
        else:
            parts.append("Evaluate screen using visual cues only.")

        parts.append("Return the verdict in the specified JSON format.")
        return "\n\n".join(parts)


    def build_qwen_chat_input(
        self,
        image_content: Any,
        pruned_nodes: Optional[List[PrunedNode]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Builds HuggingFace / Qwen2-VL chat format messages list.
        """
        user_text = self.build_user_prompt(pruned_nodes, metadata)

        messages: List[Dict[str, Any]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "image", "image": image_content},
                {"type": "text", "text": user_text},
            ],
        })
        return messages



class VerdictParser:
    """
    Extracts, sanitizes, and parses structured Verdict instances
    from raw VLM output text streams.
    """

    @staticmethod
    def extract_json_block(text: str) -> str:
        """
        Extracts JSON substring, stripping markdown ```json fences if present.
        """
        clean = text.strip()
        # 1. Match markdown fenced JSON
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()

        # 2. Match first '{' to last '}'
        brace_match = re.search(r"(\{[\s\S]*\})", clean)
        if brace_match:
            return brace_match.group(1).strip()

        return clean

    @classmethod
    def parse(cls, raw_output: str) -> Verdict:
        """
        Parses raw LLM text into a validated Verdict Pydantic model.
        Falls back to a safe inconclusive verdict if malformed.
        """
        json_str = cls.extract_json_block(raw_output)

        try:
            data = json.loads(json_str)
            # Ensure valid defect_type enum
            defect_type_str = str(data.get("defect_type", "none")).lower().strip()
            valid_types = {e.value for e in DefectType}
            if defect_type_str not in valid_types:
                defect_type = DefectType.OTHER
                data["sub_category"] = defect_type_str
            else:
                defect_type = DefectType(defect_type_str)

            has_defect = bool(data.get("has_defect", False))
            if defect_type == DefectType.NONE:
                has_defect = False

            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            bbox = data.get("bounding_box")
            if bbox and (not isinstance(bbox, list) or len(bbox) != 4):
                bbox = None

            return Verdict(
                has_defect=has_defect,
                defect_type=defect_type,
                sub_category=data.get("sub_category"),
                confidence=confidence,
                bounding_box=bbox,
                affected_element_id=data.get("affected_element_id"),
                explanation=str(data.get("explanation", "")).strip(),
            )
        except Exception as e:
            # Graceful degradation fallback
            return Verdict(
                has_defect=False,
                defect_type=DefectType.NONE,
                confidence=0.0,
                explanation=f"Malformed VLM response fallback: {str(e)} | Raw: {raw_output[:100]}",
            )
