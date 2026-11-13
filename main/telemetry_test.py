"""
Tests for the OpenTelemetry setup that runs in deployed environments.

mitol-django-observability turns tracing on in AppConfig.ready() when an OTLP
endpoint is configured, then auto-instruments Django, psycopg, redis, requests and
celery. Tests run without an endpoint, so none of that runs in the suite, and an
instrumentor that fails only logs a warning. An OpenTelemetry upgrade that breaks
setup would ship silently and leave production with no traces.

Instrumentation patches libraries and sets a process-wide tracer provider that
can't be unset, so the check runs in a fresh interpreter. Nothing is exported:
spans go to an in-memory exporter and the process exits before the batch exporter
flushes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings

RESULT_MARKER = "TELEMETRY_RESULT="

SCRIPT = f"""
import json, os, sys
import django

django.setup()

from django.conf import settings
from django.http import HttpResponse
from django.test import Client
from django.test.utils import override_settings, setup_test_environment
from django.urls import path
from opentelemetry import trace
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

def ok(request):
    return HttpResponse("ok")

urlpatterns = [path("otel-check/", ok)]

provider = trace.get_tracer_provider()
result = {{
    "provider": type(provider).__name__,
    "service_name": provider.resource.attributes.get("service.name")
    if isinstance(provider, TracerProvider) else None,
    "instrumented": {{
        name: instrumentor().is_instrumented_by_opentelemetry
        for name, instrumentor in [
            ("django", DjangoInstrumentor),
            ("psycopg", PsycopgInstrumentor),
            ("redis", RedisInstrumentor),
            ("requests", RequestsInstrumentor),
            ("celery", CeleryInstrumentor),
        ]
    }},
    "first_middleware": settings.MIDDLEWARE[0],
    "spans": [],
}}

if isinstance(provider, TracerProvider):
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    setup_test_environment()
    # Only the middleware DjangoInstrumentor inserted, so the request needs no database.
    with override_settings(MIDDLEWARE=[settings.MIDDLEWARE[0]], ROOT_URLCONF="__main__"):
        status = Client().get("/otel-check/").status_code
    result["status"] = status
    result["spans"] = [
        {{
            "name": span.name,
            "kind": span.kind.name,
            "route": span.attributes.get("http.route"),
            "status_code": span.attributes.get("http.response.status_code",
                span.attributes.get("http.status_code")),
        }}
        for span in exporter.get_finished_spans()
    ]

print("{RESULT_MARKER}" + json.dumps(result), flush=True)
sys.stdout.flush()
os._exit(0)
"""


def _run_with_telemetry_enabled():
    """Boot Django in a fresh interpreter with an OTLP endpoint configured."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "main.settings",
        # Unroutable on purpose; the process exits before anything is exported.
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://127.0.0.1:9/v1/traces",
        "OTEL_SERVICE_NAME": "mitxonline-telemetry-test",
    }
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", SCRIPT],
        cwd=Path(settings.BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    result_lines = [
        line for line in completed.stdout.splitlines() if line.startswith(RESULT_MARKER)
    ]
    assert result_lines, output
    return json.loads(result_lines[-1].removeprefix(RESULT_MARKER)), output


def test_telemetry_instruments_and_traces_requests():
    """With an endpoint set, startup should instrument every library and trace requests."""
    result, output = _run_with_telemetry_enabled()

    assert "Failed to auto-instrument" not in output
    assert result["provider"] == "TracerProvider"
    assert result["service_name"] == "mitxonline-telemetry-test"
    assert result["instrumented"] == {
        "django": True,
        "psycopg": True,
        "redis": True,
        "requests": True,
        "celery": True,
    }
    assert "opentelemetry" in result["first_middleware"]

    assert result["status"] == 200
    server_spans = [span for span in result["spans"] if span["kind"] == "SERVER"]
    assert len(server_spans) == 1
    assert server_spans[0]["route"] == "otel-check/"
    assert server_spans[0]["status_code"] == 200
