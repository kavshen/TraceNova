"""Heuristic root-cause analysis engine for TraceNova (Phase 8).

Scores candidate causes from fixed, human-authored rules over detection signals --
deterministic and explainable, and runs before any LLM-assisted RCA (Phase 13).
Every cause reports which signals contributed to its score, what evidence is
still missing to confirm it, and which rule IDs fired, so results stay auditable
even without a database/dependency/deployment data source yet.
"""

from datetime import UTC, datetime

from tracenova_api.models import (
    CauseScore,
    DegradationReport,
    DetectionSignal,
    RCACause,
    RCAResult,
    SignalSeverity,
    SignalType,
)

_MAX_SCORE = 1.0


def _find(signals: list[DetectionSignal], signal_type: SignalType) -> DetectionSignal | None:
    """Return the signal of a given type, if present."""
    for signal in signals:
        if signal.signal_type == signal_type:
            return signal
    return None


def _is_high(signal: DetectionSignal | None) -> bool:
    """Whether a signal exists and is at HIGH severity."""
    return signal is not None and signal.severity == SignalSeverity.HIGH


class RCAEngine:
    """Deterministic, rule-based root-cause scoring from detection signals."""

    @staticmethod
    def analyze(report: DegradationReport) -> RCAResult:
        """Score all known candidate causes against a degradation report's signals."""
        signals = report.signals
        duration = _find(signals, SignalType.DURATION_DEGRADATION)
        failure = _find(signals, SignalType.FAILURE_RATE_INCREASE)
        retry = _find(signals, SignalType.RETRY_RATE_INCREASE)
        throughput = _find(signals, SignalType.THROUGHPUT_DECREASE)

        causes = [
            RCAEngine._score_retry_storm(retry, duration),
            RCAEngine._score_database_bottleneck(duration, retry, throughput),
            RCAEngine._score_upstream_api_failure(failure, throughput),
            RCAEngine._score_compute_saturation(duration, throughput),
            RCAEngine._score_network_latency(duration, failure),
            RCAEngine._score_dependency_failure(failure, throughput),
            RCAEngine._score_resource_exhaustion(throughput, duration),
            RCAEngine._score_recent_deployment(),
        ]
        causes.sort(key=lambda c: c.score, reverse=True)

        return RCAResult(
            pipeline_id=report.pipeline_id,
            causes=causes,
            evaluated_at=datetime.now(UTC),
        )

    @staticmethod
    def _score_retry_storm(
        retry: DetectionSignal | None,
        duration: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []
        missing: list[str] = []

        if retry is not None:
            score += 0.5
            contributing.append(SignalType.RETRY_RATE_INCREASE)
            rule_ids.append("RETRY_STORM_BASE")
            if _is_high(retry):
                score += 0.2
                rule_ids.append("RETRY_STORM_HIGH_SEVERITY")
        else:
            missing.append("No retry-rate signal present.")

        if retry is not None and duration is not None:
            score += 0.15
            contributing.append(SignalType.DURATION_DEGRADATION)
            rule_ids.append("RETRY_STORM_DURATION_COMPOUND")

        missing.append("Retry burst/timing data not yet available to confirm storm pattern.")

        return CauseScore(
            cause=RCACause.RETRY_STORM,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=missing,
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_database_bottleneck(
        duration: DetectionSignal | None,
        retry: DetectionSignal | None,
        throughput: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []

        if duration is not None:
            score += 0.35
            contributing.append(SignalType.DURATION_DEGRADATION)
            rule_ids.append("DB_BOTTLENECK_DURATION_BASE")
            if _is_high(duration):
                score += 0.15
                rule_ids.append("DB_BOTTLENECK_DURATION_HIGH_SEVERITY")
        if retry is not None:
            score += 0.15
            contributing.append(SignalType.RETRY_RATE_INCREASE)
            rule_ids.append("DB_BOTTLENECK_RETRY_COMPOUND")
        if throughput is not None:
            score += 0.15
            contributing.append(SignalType.THROUGHPUT_DECREASE)
            rule_ids.append("DB_BOTTLENECK_THROUGHPUT_COMPOUND")

        return CauseScore(
            cause=RCACause.DATABASE_BOTTLENECK,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=["No direct database latency/connection-pool metric available yet."],
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_upstream_api_failure(
        failure: DetectionSignal | None,
        throughput: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []

        if failure is not None:
            score += 0.4
            contributing.append(SignalType.FAILURE_RATE_INCREASE)
            rule_ids.append("UPSTREAM_API_FAILURE_BASE")
            if _is_high(failure):
                score += 0.2
                rule_ids.append("UPSTREAM_API_FAILURE_HIGH_SEVERITY")
        if throughput is not None:
            score += 0.1
            contributing.append(SignalType.THROUGHPUT_DECREASE)
            rule_ids.append("UPSTREAM_API_FAILURE_THROUGHPUT_COMPOUND")

        return CauseScore(
            cause=RCACause.UPSTREAM_API_FAILURE,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=["No upstream service/dependency health data available yet."],
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_compute_saturation(
        duration: DetectionSignal | None,
        throughput: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []

        if duration is not None:
            score += 0.25
            contributing.append(SignalType.DURATION_DEGRADATION)
            rule_ids.append("COMPUTE_SATURATION_DURATION_BASE")
        if throughput is not None:
            score += 0.25
            contributing.append(SignalType.THROUGHPUT_DECREASE)
            rule_ids.append("COMPUTE_SATURATION_THROUGHPUT_BASE")
            if _is_high(throughput):
                score += 0.15
                rule_ids.append("COMPUTE_SATURATION_THROUGHPUT_HIGH_SEVERITY")

        return CauseScore(
            cause=RCACause.COMPUTE_SATURATION,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=["No CPU/memory resource utilization metrics available yet."],
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_network_latency(
        duration: DetectionSignal | None,
        failure: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []

        if duration is not None and not _is_high(duration):
            score += 0.2
            contributing.append(SignalType.DURATION_DEGRADATION)
            rule_ids.append("NETWORK_LATENCY_MODERATE_DURATION")
        if failure is not None:
            score += 0.15
            contributing.append(SignalType.FAILURE_RATE_INCREASE)
            rule_ids.append("NETWORK_LATENCY_FAILURE_COMPOUND")

        return CauseScore(
            cause=RCACause.NETWORK_LATENCY,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=["No network-level telemetry (latency, packet loss) available yet."],
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_dependency_failure(
        failure: DetectionSignal | None,
        throughput: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []

        if failure is not None:
            score += 0.3
            contributing.append(SignalType.FAILURE_RATE_INCREASE)
            rule_ids.append("DEPENDENCY_FAILURE_BASE")
            if _is_high(failure):
                score += 0.15
                rule_ids.append("DEPENDENCY_FAILURE_HIGH_SEVERITY")
        if throughput is not None:
            score += 0.2
            contributing.append(SignalType.THROUGHPUT_DECREASE)
            rule_ids.append("DEPENDENCY_FAILURE_THROUGHPUT_COMPOUND")

        return CauseScore(
            cause=RCACause.DEPENDENCY_FAILURE,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=[
                "No dependency graph available yet to confirm which dependency failed."
            ],
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_resource_exhaustion(
        throughput: DetectionSignal | None,
        duration: DetectionSignal | None,
    ) -> CauseScore:
        score = 0.0
        contributing: list[SignalType] = []
        rule_ids: list[str] = []

        if throughput is not None:
            score += 0.3
            contributing.append(SignalType.THROUGHPUT_DECREASE)
            rule_ids.append("RESOURCE_EXHAUSTION_BASE")
            if _is_high(throughput):
                score += 0.2
                rule_ids.append("RESOURCE_EXHAUSTION_HIGH_SEVERITY")
        if duration is not None:
            score += 0.2
            contributing.append(SignalType.DURATION_DEGRADATION)
            rule_ids.append("RESOURCE_EXHAUSTION_DURATION_COMPOUND")

        return CauseScore(
            cause=RCACause.RESOURCE_EXHAUSTION,
            score=round(min(score, _MAX_SCORE), 4),
            contributing_signals=contributing,
            missing_evidence=["No CPU/memory/disk utilization metrics available yet."],
            rule_ids=rule_ids,
        )

    @staticmethod
    def _score_recent_deployment() -> CauseScore:
        """No deployment metadata exists anywhere in the system yet.

        Always returned at score 0 with no supporting rules, so RECENT_DEPLOYMENT
        is explicitly visible as unconfirmable rather than silently omitted.
        """
        return CauseScore(
            cause=RCACause.RECENT_DEPLOYMENT,
            score=0.0,
            contributing_signals=[],
            missing_evidence=[
                "No deployment event tracking exists yet; this cause cannot be "
                "scored until deployment metadata is introduced."
            ],
            rule_ids=[],
        )