from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)


class MetricsRegistry:

    def __init__(
                self,
                registry=None,
                ):

        self.registry = (
                        registry
                        or CollectorRegistry()
                        )

        self.calls_total = Counter(
                                    "atlas_tool_calls_total",
                                    "Total tool invocations.",
                                    ["tool", "status"],
                                    registry=self.registry,
                                )

        self.latency = Histogram(
                                "atlas_tool_latency_seconds",
                                "End-to-end tool latency.",
                                ["tool"],
                                buckets=(
                                    0.005,
                                    0.01,
                                    0.025,
                                    0.05,
                                    0.1,
                                    0.25,
                                    0.5,
                                    1,
                                    2.5,
                                    5,
                                    10,
                                    30,
                                ),
                                registry=self.registry,
                            )

        self.cache_hit = Counter(
                                "atlas_cache_hits_total",
                                "Cache hits (L1 + L2).",
                                ["tool"],
                                registry=self.registry,
                                )

        self.cache_miss = Counter(
                                "atlas_cache_misses_total",
                                "Cache misses that hit the tool.",
                                ["tool"],
                                registry=self.registry,
                                )

        self.rate_limited = Counter(
                                    "atlas_rate_limited_total",
                                    "Requests rejected by the rate limiter.",
                                    ["tool"],
                                    registry=self.registry,
                                )

        self.circuit_state = Gauge(
                                    "atlas_circuit_state",
                                    "Circuit state (0=closed, 1=half_open, 2=open).",
                                    ["tool"],
                                    registry=self.registry,
                                )

        self.active_sessions = Gauge(
                                    "atlas_active_sessions",
                                    "Active MCP sessions on this replica.",
                                    registry=self.registry,
                                )