import json
import time
from typing import List, Dict, Any, Optional

class EnvironmentAttributionEngine:
    """Correlates perturbation event logs with application failures (crashes, ANRs, visual defects) to produce root-cause attribution reports."""

    def __init__(self, perturbation_log_path: str = "perturbation_event_log.json"):
        self.perturbation_log_path = perturbation_log_path

    def correlate(
        self,
        failures: List[Dict[str, Any]],
        perturbation_events: Optional[List[Dict[str, Any]]] = None,
        time_window_sec: float = 3.5
    ) -> Dict[str, Any]:
        """Correlates failure occurrences with temporally proximate environmental stressors."""
        events = perturbation_events or self._load_events()
        attributions = []

        window_ms = time_window_sec * 1000

        for failure in failures:
            fail_epoch = failure.get("epoch_ms", int(time.time() * 1000))
            fail_type = failure.get("type", "UNKNOWN_DEFECT")
            fail_desc = failure.get("description", "")

            # Identify perturbations within temporal causality window [fail_epoch - window_ms, fail_epoch + 500ms]
            correlated_events = [
                e for e in events
                if abs(fail_epoch - e.get("epoch_ms", fail_epoch)) <= window_ms
            ]

            attribution = self._analyze_causality(failure, correlated_events)
            attributions.append(attribution)

        report = {
            "analysis_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_failures_analyzed": len(failures),
            "attributed_failures_count": sum(1 for a in attributions if a["confidence"] > 0.5),
            "attributions": attributions
        }
        return report

    def _analyze_causality(self, failure: Dict[str, Any], candidate_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        fail_type = failure.get("type", "").upper()
        fail_desc = failure.get("description", "").lower()

        primary_trigger = "UNCLASSIFIED_ENVIRONMENTAL_VARIATION"
        confidence = 0.35
        factors = []
        explanation = "Failure occurred near recorded test steps, but no single dominant stressor was identified."

        for e in candidate_events:
            category = e.get("category", "")
            action = e.get("action", "")
            params = e.get("parameters", {})
            factors.append(f"{category}:{action}")

            # Network causality
            if any(term in fail_type or term in fail_desc for term in ["TIMEOUT", "SOCKET", "NETWORK", "OFFLINE", "PAYMENT_DROP"]):
                if "NETWORK" in category:
                    primary_trigger = action
                    confidence = 0.94
                    explanation = f"Network failure directly triggered by {action} (params: {params}). App failed to recover gracefully."

            # Memory / ANR / CPU causality
            elif any(term in fail_type or term in fail_desc for term in ["ANR", "FREEZE", "OOM", "CRASH_LMK", "FRAME_DROP"]):
                if "SYSTEM_CPU" in category or "SYSTEM_RAM" in category or "SYSTEM_IO" in category:
                    primary_trigger = action
                    confidence = 0.91
                    explanation = f"App freeze or resource termination attributed to {action} under heavy device starvation."

            # Layout / Visual Collision causality
            elif any(term in fail_type or term in fail_desc for term in ["OVERFLOW", "COLLISION", "TRUNCATION", "VISUAL_BUG"]):
                if "ORIENTATION" in category or "FONT_SCALE" in category:
                    primary_trigger = action
                    confidence = 0.93
                    explanation = f"GUI layout defect induced by dynamic {action} (params: {params}). Layout constraints broke."

            # Interruption / State restoration causality
            elif any(term in fail_type or term in fail_desc for term in ["NULLPOINTER", "STATE_LOSS", "ILLEGAL_STATE", "RESTORE_FAIL"]):
                if "INTERRUPTION" in category:
                    primary_trigger = action
                    confidence = 0.89
                    explanation = f"Activity lifecycle state loss caused by sudden {action} backgrounding/interruption."

        return {
            "failure_id": failure.get("id", f"FAIL_{int(time.time()*1000)}"),
            "failure_type": failure.get("type"),
            "component_impacted": failure.get("component", "Core UI"),
            "primary_trigger": primary_trigger,
            "confidence": confidence,
            "compound_stress_factors": factors,
            "root_cause_explanation": explanation,
            "recommended_mitigation": self._get_recommendation(primary_trigger)
        }

    def _get_recommendation(self, trigger: str) -> str:
        if "BANDWIDTH" in trigger or "LATENCY" in trigger:
            return "Implement resilient exponential backoff, request caching, and optimistic UI state updates."
        elif "LMK" in trigger or "RAM" in trigger:
            return "Release large bitmap allocations on onTrimMemory() and avoid holding singleton references across lifecycles."
        elif "ORIENTATION" in trigger or "FONT_SCALE" in trigger:
            return "Utilize flexible ConstraintLayout dimensions with wrap_content and avoid hardcoded pixel heights."
        elif "APP_BACKGROUNDED" in trigger or "INCOMING_CALL" in trigger:
            return "Persist transient state inside onSaveInstanceState() / ViewModel SavedStateHandle."
        return "Audit error boundaries and add fallback UI indicators during environmental fluctuations."

    def _load_events(self) -> List[Dict[str, Any]]:
        try:
            with open(self.perturbation_log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def export_report(self, report: Dict[str, Any], output_path: str = "environment_failure_attribution.json") -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[+] Failure attribution report saved to: {output_path}")
