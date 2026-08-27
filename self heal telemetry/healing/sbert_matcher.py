import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

class SBERTSemanticMatcher:
    """Sentence-BERT semantic embedding engine for locator self-healing [23]."""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        print(f"[S-BERT] Initializing Semantic Embedding Model: {model_name}...")
        self.model = SentenceTransformer(model_name)

    def compute_similarity(self, target_text: str, candidate_texts: List[str]) -> np.ndarray:
        target_vec = self.model.encode(target_text, convert_to_numpy=True)
        candidate_vecs = self.model.encode(candidate_texts, convert_to_numpy=True)

        target_norm = target_vec / np.linalg.norm(target_vec)
        cand_norm = candidate_vecs / np.linalg.norm(candidate_vecs, axis=1, keepdims=True)

        return np.dot(cand_norm, target_norm)

    def find_best_candidate(self, target_label: str, candidates: List[Dict[str, Any]], threshold: float = 0.40):
        if not candidates:
            return None, 0.0

        descriptions = [c["clean_descriptor"] for c in candidates]
        scores = self.compute_similarity(target_label, descriptions)

        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score >= threshold:
            return candidates[best_idx], best_score
        return candidates[best_idx], best_score
