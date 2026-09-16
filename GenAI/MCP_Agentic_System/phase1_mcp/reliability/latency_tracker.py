from collections import defaultdict, deque
import statistics


class LatencyTracker:
    def __init__(
            self, 
            max_samples_per_tool: int = 100
            ):
        
        if max_samples_per_tool < 1:
            raise ValueError("max_samples_per_tool must be >= 1")

        self.max_samples_per_tool = max_samples_per_tool
        self._samples = defaultdict(
            lambda: deque(
                maxlen=max_samples_per_tool
                )
            )

    def record(
            self, 
            tool_name: str, 
            duration_seconds: float
            ) -> None:
        
        if duration_seconds < 0:
            raise ValueError("duration_seconds must be >= 0")

        self._samples[tool_name].append(duration_seconds)

    def get_samples(
            self, 
            tool_name: str
            ) -> list[float]:
        
        return list(self._samples.get(tool_name, []))

    def get_percentile(
        self,
        tool_name: str,
        percentile: float = 95.0,
    ) -> float | None:
        
        if not 0 < percentile <= 100:
            raise ValueError("percentile must be in the range (0, 100]")

        samples = self.get_samples(tool_name)

        if not samples:
            return None

        if len(samples) == 1:
            return samples[0]

        return statistics.quantiles(
            samples,
            n=100,
            method="inclusive",
        )[int(percentile) - 1]