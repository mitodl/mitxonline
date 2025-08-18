"""OpenTelemetry initialization and configuration for MITxOnline."""

from __future__ import annotations

import logging

from django.conf import settings
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as OTLPSpanExporterGrpc,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

log = logging.getLogger(__name__)


def configure_opentelemetry() -> TracerProvider | None:
    """
    Configure OpenTelemetry with appropriate instrumentations and exporters.
    Returns the tracer provider if configured, None otherwise.
    """
    if not getattr(settings, "OPENTELEMETRY_ENABLED", False):
        log.info("OpenTelemetry is disabled")
        return None

    log.info("Initializing OpenTelemetry")

    # Create a resource with service info
    resource = Resource.create(
        {
            "service.name": getattr(
                settings, "OPENTELEMETRY_SERVICE_NAME", "mitxonline"
            ),
            "service.version": getattr(settings, "VERSION", "unknown"),
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    # Configure the tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Add console exporter for development/testing
    if settings.DEBUG:
        log.info("Adding console exporter for OpenTelemetry")
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Add OTLP exporter if configured
    otlp_endpoint = getattr(settings, "OPENTELEMETRY_ENDPOINT", None)
    if otlp_endpoint:
        log.info("Configuring OTLP exporter to endpoint: %s", otlp_endpoint)

        headers = {}

        try:
            use_grpc = getattr(settings, "OPENTELEMETRY_USE_GRPC", False)
            if use_grpc:
                otlp_exporter = OTLPSpanExporterGrpc(
                    endpoint=otlp_endpoint,
                    headers=headers,
                    insecure=getattr(settings, "OPENTELEMETRY_INSECURE", True),
                )
            else:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint,
                    headers=headers,
                )

            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    otlp_exporter,
                    max_export_batch_size=getattr(
                        settings, "OPENTELEMETRY_BATCH_SIZE", 512
                    ),
                    schedule_delay_millis=getattr(
                        settings, "OPENTELEMETRY_EXPORT_TIMEOUT_MS", 5000
                    ),
                )
            )
        except Exception:
            log.exception("Failed to configure OTLP exporter")

    # Initialize instrumentations
    DjangoInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()
    RequestsInstrumentor().instrument()

    log.info("OpenTelemetry initialized successfully")
    return tracer_provider
