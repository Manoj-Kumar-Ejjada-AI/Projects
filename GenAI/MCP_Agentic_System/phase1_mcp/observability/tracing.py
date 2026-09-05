from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)
from opentelemetry.trace import Status, StatusCode


_INITIALISED = False


def init_tracing(
    service_name: str,
    otel_endpoint: str,
    ):

    global _INITIALISED

    if _INITIALISED:
        return

    resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": "0.1.0",
            }
        )

    provider = TracerProvider(
            resource=resource
        )

    exporter = OTLPSpanExporter(
            endpoint=otel_endpoint,
            insecure=True,
        )

    provider.add_span_processor(
            BatchSpanProcessor(exporter)
        )

    trace.set_tracer_provider(
            provider
        )

    _INITIALISED = True


def get_tracer():

    return trace.get_tracer(
            "mcp-agentic-system"
        )


def current_trace_id():

    span = trace.get_current_span()

    if (
            span is None
            or not span.is_recording()
        ):
        return None

    context = (
        span.get_span_context()
    )

    if not context.is_valid:
        return None

    return f"{context.trace_id:032x}"



def record_span_error(
        span, 
        error
        ):
    try:
        span.record_exception(error)
        span.set_status(
            Status(
                StatusCode.ERROR,
                str(error)
            )
        )
    except Exception:
        pass
