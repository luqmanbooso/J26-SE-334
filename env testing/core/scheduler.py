import time
import threading
from typing import Callable, Dict, List, Any, Optional

class PerturbationScheduler:
    """Orchestrates dynamic perturbation scheduling based on test-step semantics and performance signals."""

    def __init__(self, logger=None):
        self.logger = logger
        self.stage_hooks: Dict[str, List[Dict[str, Any]]] = {}
        self.signal_thresholds = {
            "fps_min": 35.0,
            "latency_max_ms": 1200.0,
            "cpu_max_pct": 85.0
        }
        self.active_escalations: List[str] = []

    def register_step_hook(
        self,
        semantic_step: str,
        action_fn: Callable[..., Any],
        params: Dict[str, Any],
        delay_sec: float = 0.0
    ) -> None:
        """Registers a perturbation hook to fire at a specific semantic test step."""
        step_key = semantic_step.upper()
        if step_key not in self.stage_hooks:
            self.stage_hooks[step_key] = []
        self.stage_hooks[step_key].append({
            "action": action_fn,
            "params": params,
            "delay": delay_sec
        })

    def trigger_step(self, semantic_step: str, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Dispatches perturbations registered for the given semantic step (e.g., MID_TRANSACTION)."""
        step_key = semantic_step.upper()
        results = []
        hooks = self.stage_hooks.get(step_key, [])

        if not hooks:
            return results

        print(f"[Scheduler] Executing {len(hooks)} perturbation hook(s) for semantic step: '{step_key}'")
        for hook in hooks:
            if hook["delay"] > 0:
                time.sleep(hook["delay"])
            try:
                fn = hook["action"]
                params = dict(hook["params"])
                if context:
                    params["_context"] = context
                res = fn(**params)
                results.append(res)
            except Exception as e:
                print(f"[Scheduler Error] Hook failure at step '{step_key}': {str(e)}")

        return results

    def evaluate_performance_signals(self, signals: Dict[str, float], on_escalate: Optional[Callable[[str], None]] = None) -> bool:
        """Evaluates runtime signals (FPS, Latency, CPU) and adapts perturbation intensity."""
        fps = signals.get("fps", 60.0)
        latency = signals.get("latency_ms", 100.0)
        cpu = signals.get("cpu_pct", 30.0)

        escalated = False

        if fps < self.signal_thresholds["fps_min"]:
            escalation_msg = f"FRAME_LAG_DETECTED: FPS dropped to {fps:.1f} (< {self.signal_thresholds['fps_min']})"
            self.active_escalations.append(escalation_msg)
            print(f"[Scheduler Signal] {escalation_msg} -> Escalating hardware pressure")
            if on_escalate:
                on_escalate("HARDWARE_ESCALATION")
            escalated = True

        if latency > self.signal_thresholds["latency_max_ms"]:
            escalation_msg = f"HIGH_LATENCY_DETECTED: Network RTT {latency:.1f}ms (> {self.signal_thresholds['latency_max_ms']}ms)"
            self.active_escalations.append(escalation_msg)
            print(f"[Scheduler Signal] {escalation_msg} -> Escalating packet throttle")
            if on_escalate:
                on_escalate("NETWORK_ESCALATION")
            escalated = True

        return escalated

    def reset(self) -> None:
        """Clears all registered hooks and active escalations."""
        self.stage_hooks.clear()
        self.active_escalations.clear()
