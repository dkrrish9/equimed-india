"""Observer Pattern implementation for audit logging, clinical telemetry, and savings tracking."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Deque, Dict, List, Optional


class SubstitutionObserver(ABC):
    """Observer interface for receiving events from the substitution engine."""

    @abstractmethod
    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle incoming engine event."""
        pass


class AuditLogObserver(SubstitutionObserver):
    """Maintains a bounded, structured in-memory audit log of clinical queries and matches."""

    def __init__(self, maxlen: int = 10000) -> None:
        self.logs: Deque[Dict[str, Any]] = deque(maxlen=maxlen)

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event_type,
            "data": payload,
        }
        self.logs.append(entry)

    def get_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        items = list(self.logs)
        if limit is not None:
            return items[-limit:]
        return items

    def clear(self) -> None:
        self.logs.clear()


class SavingsTrackerObserver(SubstitutionObserver):
    """Aggregates economic metrics on consumer savings."""

    def __init__(self) -> None:
        self.total_queries: int = 0
        self.total_substitutions_found: int = 0
        self.cumulative_potential_savings: float = 0.0
        self.max_savings_percentage: float = 0.0

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if event_type == "SUBSTITUTION_FOUND":
            self.total_queries += 1
            savings_pct = float(payload.get("percentage_savings", 0.0))
            savings_rupees = float(payload.get("savings_per_unit", 0.0))
            self.total_substitutions_found += 1
            self.cumulative_potential_savings += savings_rupees
            if savings_pct > self.max_savings_percentage:
                self.max_savings_percentage = savings_pct

        elif event_type == "BASKET_OPTIMIZED":
            saved = float(payload.get("monthly_savings_amount", 0.0))
            self.cumulative_potential_savings += saved

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "total_substitutions_found": self.total_substitutions_found,
            "cumulative_potential_savings": round(self.cumulative_potential_savings, 2),
            "max_savings_percentage": round(self.max_savings_percentage, 2),
        }

    def reset(self) -> None:
        self.total_queries = 0
        self.total_substitutions_found = 0
        self.cumulative_potential_savings = 0.0
        self.max_savings_percentage = 0.0


class SafetyAlertObserver(SubstitutionObserver):
    """Tracks safety warnings, NTI alerts, and bounded bioequivalence rejection logs."""

    def __init__(self, maxlen: int = 10000) -> None:
        self.nti_alerts_count: int = 0
        self.rejection_count: int = 0
        self.warnings_logged: Deque[Dict[str, Any]] = deque(maxlen=maxlen)

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if event_type == "SUBSTITUTION_REJECTED":
            self.rejection_count += 1
            self.warnings_logged.append({
                "type": "REJECTION",
                "reason": payload.get("reason"),
                "candidate": payload.get("candidate"),
            })
        elif event_type == "SAFETY_WARNING":
            warnings = payload.get("warnings", [])
            for w in warnings:
                if "Narrow Therapeutic Index" in w:
                    self.nti_alerts_count += 1
                self.warnings_logged.append({
                    "type": "WARNING",
                    "text": w,
                    "medicine": payload.get("medicine"),
                })

    def get_summary(self) -> Dict[str, Any]:
        return {
            "nti_alerts_count": self.nti_alerts_count,
            "rejection_count": self.rejection_count,
            "total_warnings": len(self.warnings_logged),
        }


class ObservableSubject:
    """Subject base class for managing observer subscriptions."""

    def __init__(self) -> None:
        self._observers: List[SubstitutionObserver] = []

    def attach(self, observer: SubstitutionObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: SubstitutionObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event_type: str, payload: Dict[str, Any]) -> None:
        for obs in self._observers:
            try:
                obs.on_event(event_type, payload)
            except Exception:
                # Observers must never interrupt the primary clinical flow
                pass
