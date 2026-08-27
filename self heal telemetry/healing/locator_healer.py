import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from healing.sbert_matcher import SBERTSemanticMatcher

class LocatorHealer:
    """Extracts live UI candidate nodes and heals broken telemetry locators using Sentence-BERT."""
    def __init__(self, matcher: SBERTSemanticMatcher):
        self.matcher = matcher

    def _sanitize_tokens(self, text: str) -> str:
        text = text.split("/")[-1]
        text = re.sub(r'^(btn_|action_|id_|view_|icon_)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'(_|-)', ' ', text)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        return text.strip()

    def extract_live_candidates(self, xml_path: str = "window_dump.xml") -> List[Dict[str, Any]]:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        candidates = []

        for node in root.iter("node"):
            bounds = node.attrib.get("bounds", "")
            text = node.attrib.get("text", "").strip()
            res_id = node.attrib.get("resource-id", "").strip()
            desc = node.attrib.get("content-desc", "").strip()
            clickable = node.attrib.get("clickable", "false")

            match = re.findall(r"\[(\d+),(\d+)\]", bounds)
            if len(match) == 2:
                x1, y1 = int(match[0][0]), int(match[0][1])
                x2, y2 = int(match[1][0]), int(match[1][1])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                clean_text = self._sanitize_tokens(text)
                clean_desc = self._sanitize_tokens(desc)
                clean_id = self._sanitize_tokens(res_id)
                clean_descriptor = " ".join(filter(None, [clean_text, clean_desc, clean_id]))

                if clean_descriptor:
                    candidates.append({
                        "descriptor": clean_descriptor,
                        "clean_descriptor": clean_descriptor,
                        "raw_text": text,
                        "res_id": res_id,
                        "desc": desc,
                        "bounds": (x1, y1, x2, y2),
                        "center": (cx, cy),
                        "clickable": clickable
                    })
        return candidates

    def resolve_locator(self, original_locator: Dict[str, str], xml_path: str = "window_dump.xml", threshold: float = 0.30):
        candidates = self.extract_live_candidates(xml_path)

        # 1. Exact match fast-path
        target_text = original_locator.get("text", "").strip()
        target_id = original_locator.get("resource_id", "").strip()

        for c in candidates:
            if (target_text and c["raw_text"] == target_text) or (target_id and c["res_id"] == target_id):
                return c, 1.0, "EXACT_MATCH"

        # 2. Semantic S-BERT Self-Healing
        clean_target = " ".join(filter(None, [
            self._sanitize_tokens(target_text),
            self._sanitize_tokens(original_locator.get("content_desc", "")),
            self._sanitize_tokens(target_id)
        ]))

        best_candidate, score = self.matcher.find_best_candidate(clean_target, candidates, threshold=threshold)

        if score >= threshold:
            return best_candidate, score, "SELF_HEALED_VIA_SBERT"
        return None, score, "FAILED_TO_RESOLVE"
