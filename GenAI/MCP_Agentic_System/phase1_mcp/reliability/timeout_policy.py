from reliability.latency_tracker import LatencyTracker

class TimeoutPolicy:
    def __init__(
        self,
        default_timeout_seconds: float = 10.0,
        min_timeout_seconds: float = 0.1,
        max_timeout_seconds: float = 10.0,
        percentile: float = 95.0,
        safety_factor: float = 3.0,
        latency_tracker: LatencyTracker = None,
        min_samples: int = 5
    ):
        if default_timeout_seconds <= 0:
            raise ValueError(
                "default_timeout_seconds must be > 0"
            )

        if min_timeout_seconds <= 0:
            raise ValueError(
                "min_timeout_seconds must be > 0"
            )

        if max_timeout_seconds < min_timeout_seconds:
            raise ValueError(
                "max_timeout_seconds must be >= min_timeout_seconds"
            )

        if safety_factor <= 0:
            raise ValueError(
                "safety_factor must be > 0"
            )

        if min_samples < 1:
            raise ValueError(
                "mi_samples must be >= 1"
            )

        self.default_timeout_seconds = default_timeout_seconds
        self.min_timeout_seconds = min_timeout_seconds
        self.max_timeout_seconds = max_timeout_seconds
        self.percentile = percentile
        self.safety_factor = safety_factor
        self.latency_tracker = latency_tracker
        self.min_samples = min_samples

    def get_timeout(
        self,
        tool_name: str,
        remaining_budget: float,
    ) -> float:
        if remaining_budget <= 0:
            return 0.0

        samples = self.latency_tracker.get_samples(tool_name)

        if len(samples) < self.min_samples:
            timeout = self.default_timeout_seconds
        else:
            percentile_latency = self.latency_tracker.get_percentile(
                tool_name,
                self.percentile
                )

            if percentile_latency is None:
                timeout = self.default_timeout_seconds
            else:
                timeout = (
                    percentile_latency * self.safety_factor
                )


        timeout = max(
            self.min_timeout_seconds,
            timeout,
        )

        timeout = min(
            self.max_timeout_seconds,
            timeout,
        )

        timeout = min(
            timeout,
            remaining_budget,
        )

        return timeout