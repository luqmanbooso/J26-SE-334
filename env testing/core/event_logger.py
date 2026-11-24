import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
try:
    import psutil
except ImportError:
    psutil = None

class EventLogger:
    """Logs timestamped perturbation events with runtime telemetry for failure attribution.
    
    Tracks injection latency (<100ms) and host system overhead (<15%) per HEART Proposal Section 2.
    """

    def __init__(
        self,
        output_path: str = "perturbation_event_log.json",
        latency_provider: Optional[Callable[[], float]] = None,
    ):
        self.output_path = output_path
        self.events: List[Dict[str, Any]] = []
        self.latency_provider = latency_provider

    def begin_action(self) -> None:
        """Marks the start of an injection operation for accurate execution timing."""
        self._action_start_t = time.perf_counter()

    def record(
        self,
        category: str,
        action: str,
        parameters: Dict[str, Any],
        status: str = "APPLIED",
        telemetry_snapshot: Optional[Dict[str, Any]] = None,
        injection_latency_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """Records an environmental perturbation event with high-precision timestamp and host overhead."""
        epoch_ms = int(time.time() * 1000)
        timestamp_iso = datetime.now().isoformat()

        # Measure host injector process overhead defensively (CPU % normalized by logical cores)
        host_cpu = 0.0
        host_mem = 0.0
        if psutil is not None:
            try:
                proc = getattr(self, "_proc", None)
                if proc is None and hasattr(psutil, "Process"):
                    proc = psutil.Process()
                    self._proc = proc
                if proc is not None and callable(getattr(proc, "cpu_percent", None)):
                    raw_cpu = float(proc.cpu_percent(interval=None))
                    cores = float(psutil.cpu_count() or 1)
                    host_cpu = round(raw_cpu / max(1.0, cores), 2)
                fn_mem = getattr(psutil, "virtual_memory", None)
                if callable(fn_mem):
                    host_mem = float(fn_mem().percent)
            except Exception:
                pass

        now_perf = time.perf_counter()
        action_start = getattr(self, "_action_start_t", None)
        self._action_start_t = None
        provider_val = self.latency_provider() if callable(self.latency_provider) else None
        if injection_latency_ms is not None:
            latency = round(float(injection_latency_ms), 2)
        elif action_start is not None:
            latency = round(max(0.0, (now_perf - action_start) * 1000.0), 2)
        elif provider_val is not None:
            latency = round(max(0.0, float(provider_val)), 2)
        else:
            latency = 0.0

        entry = {
            "epoch_ms": epoch_ms,
            "timestamp": timestamp_iso,
            "category": category,
            "action": action,
            "parameters": parameters,
            "status": status,
            "injection_latency_ms": latency,
            "latency_compliant": latency < 100.0,
            "host_overhead": {
                "cpu_percent": host_cpu,
                "mem_percent": host_mem,
                "compliant": host_cpu < 15.0
            },
            "telemetry": telemetry_snapshot or {}
        }
        self.events.append(entry)
        param_summary = ", ".join(f"{k}={v}" for k, v in parameters.items())
        print(f"[{timestamp_iso}] [{category}] {action} ({status}, {latency}ms) -> {param_summary}")
        return entry

    def get_events(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recorded events, optionally filtered by category."""
        if category:
            return [e for e in self.events if e.get("category") == category]
        return list(self.events)

    def get_recent(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Returns the most recent events."""
        return self.events[-limit:]

    def get_performance_summary(self) -> Dict[str, Any]:
        """Aggregates performance compliance metrics for Proposal RQ1 validation."""
        if not self.events:
            return {
                "total_events": 0,
                "avg_injection_latency_ms": 0.0,
                "latency_compliance_rate": 100.0,
                "avg_host_cpu_overhead": 0.0,
                "overhead_compliant": True
            }

        latencies = [e.get("injection_latency_ms", 0.0) for e in self.events]
        cpus = [e.get("host_overhead", {}).get("cpu_percent", 0.0) for e in self.events]

        avg_lat = round(sum(latencies) / len(latencies), 2)
        compliant_count = sum(1 for l in latencies if l < 100.0)
        compliance_pct = round((compliant_count / len(latencies)) * 100, 1)
        avg_cpu = round(sum(cpus) / len(cpus), 2)

        return {
            "total_events": len(self.events),
            "avg_injection_latency_ms": avg_lat,
            "latency_target_ms": 100.0,
            "latency_compliance_rate": compliance_pct,
            "avg_host_cpu_overhead": avg_cpu,
            "overhead_target_pct": 15.0,
            "overhead_compliant": avg_cpu < 15.0
        }

    def clear(self) -> None:
        """Clears in-memory events."""
        self.events = []

    def save(self) -> None:
        """Persists perturbation event log to disk."""
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)
        print(f"[+] Perturbation telemetry written ({len(self.events)} events) to: {self.output_path}")
