class TimeoutPolicy:
    def __init__(
        self,
        default_timeout_seconds: float = 10.0,
        min_timeout_seconds: float = 0.1,
        max_timeout_seconds: float = 10.0,
        percentile: float = 95.0,
        safety_factor: float = 3.0,
        latency_tracker=None,
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

        self.default_timeout_seconds = default_timeout_seconds
        self.min_timeout_seconds = min_timeout_seconds
        self.max_timeout_seconds = max_timeout_seconds
        self.percentile = percentile
        self.safety_factor = safety_factor
        self.latency_tracker = latency_tracker

    def get_timeout(
        self,
        tool_name: str,
        remaining_budget: float,
    ) -> float:
        if remaining_budget <= 0:
            return 0.0

        timeout = self.default_timeout_seconds

        if self.latency_tracker is not None:
            p95 = self.latency_tracker.get_percentile(
                tool_name,
                self.percentile,
            )

            if p95 is not None:
                timeout = p95 * self.safety_factor

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