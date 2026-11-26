import asyncio
import time
import threading
from typing import Callable, Dict, List, Any, Optional


class PerturbationScheduler:
    """Asyncio-capable timeline & semantic perturbation scheduler."""

    def __init__(self, logger=None):
        self.logger = logger
        self.stage_hooks: Dict[str, List[Dict[str, Any]]] = {}
        self.signal_thresholds = {
            "fps_min": 35.0,
            "latency_max_ms": 1200.0,
            "cpu_max_pct": 85.0,
        }
        self.active_escalations: List[str] = []

    def register_step_hook(
        self,
        semantic_step: str,
        action_fn: Callable[..., Any],
        params: Dict[str, Any],
        delay_sec: float = 0.0,
    ) -> None:
        """Registers a perturbation hook to fire at a specific semantic test step."""
        step_key = semantic_step.upper()
        self.stage_hooks.setdefault(step_key, []).append({
            "action": action_fn,
            "params": params,
            "delay": delay_sec,
        })

    def trigger_step(self, semantic_step: str, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Dispatches perturbations registered for the given semantic step synchronously."""
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
                results.append(fn(**params))
            except Exception as e:
                print(f"[Scheduler Error] Hook failure at step '{step_key}': {str(e)}")
        return results

    async def trigger_step_async(
        self,
        semantic_step: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """Concurrently dispatches registered hooks using Python asyncio tasks."""
        step_key = semantic_step.upper()
        hooks = self.stage_hooks.get(step_key, [])
        if not hooks:
            return []

        async def _run_hook(hook: Dict[str, Any]) -> Any:
            if hook["delay"] > 0:
                await asyncio.sleep(hook["delay"])
            fn = hook["action"]
            params = dict(hook["params"])
            if context:
                params["_context"] = context
            if asyncio.iscoroutinefunction(fn):
                return await fn(**params)
            return await asyncio.to_thread(fn, **params)

        results = await asyncio.gather(*(_run_hook(h) for h in hooks), return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]

    async def schedule_timeline(
        self,
        timeline: List[Dict[str, Any]],
        action_registry: Optional[Dict[str, Callable[..., Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Executes a compiled timeline concurrently via asyncio offset timers."""
        registry = action_registry or {}

        async def _run_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
            offset_ms = int(entry.get("offset_ms", 0))
            if offset_ms > 0:
                await asyncio.sleep(offset_ms / 1000.0)
            action_name = str(entry.get("action", ""))
            fn = entry.get("callable") or registry.get(action_name)
            params = dict(entry.get("params") or {})
            if context:
                params["_context"] = context
            t0 = time.perf_counter()
            status = "SKIPPED_UNKNOWN_ACTION"
            if callable(fn):
                try:
                    if asyncio.iscoroutinefunction(fn):
                        await fn(**params)
                    else:
                        await asyncio.to_thread(fn, **params)
                    status = "APPLIED"
                except Exception as exc:
                    status = f"ERROR: {exc}"
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            return {
                "offset_ms": offset_ms,
                "step": str(entry.get("step", "IMMEDIATE")),
                "action": action_name,
                "status": status,
                "dispatch_ms": elapsed_ms,
            }

        if not timeline:
            return []
        return list(await asyncio.gather(*(_run_entry(item) for item in timeline)))

    def run_timeline(
        self,
        timeline: List[Dict[str, Any]],
        action_registry: Optional[Dict[str, Callable[..., Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Runs an asyncio timeline cleanly from synchronous callers."""
        try:
            asyncio.get_running_loop()
            result_box: Dict[str, List[Dict[str, Any]]] = {}

            def _runner():
                result_box["res"] = asyncio.run(
                    self.schedule_timeline(timeline, action_registry=action_registry, context=context)
                )

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join(timeout=30.0)
            return result_box.get("res", [])
        except RuntimeError:
            return asyncio.run(
                self.schedule_timeline(timeline, action_registry=action_registry, context=context)
            )

    def evaluate_performance_signals(
        self,
        signals: Dict[str, float],
        on_escalate: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Evaluates runtime signals (FPS, Latency, CPU) and adapts perturbation intensity."""
        fps = signals.get("fps", 60.0)
        latency = signals.get("latency_ms", 100.0)

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
