"""
OpenTelemetry 遥测配置
=======================

自动追踪：HTTP 请求、数据库查询、LLM 调用（通过 LiteLLM + Langfuse）。

环境变量配置：
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
    OTEL_SERVICE_NAME=ai-python-tutor
"""

from app.observability.logger import get_logger

logger = get_logger(__name__)


def setup_opentelemetry():
    """初始化 OpenTelemetry SDK。"""
    import os

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not otel_endpoint:
        logger.info("otel_skipped", reason="未配置 OTEL_EXPORTER_OTLP_ENDPOINT，跳过")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "ai-python-tutor")})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        logger.info("otel_enabled", endpoint=otel_endpoint)
    except Exception as e:
        logger.warning("otel_setup_failed", error=str(e))


setup_opentelemetry()
