"""
OpenTelemetry Configuration for Distributed Tracing
Auto-instruments Django, PostgreSQL, Redis, and HTTP requests
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


def configure_tracing():
    """
    Configure OpenTelemetry distributed tracing.
    
    Environment Variables:
    - OTEL_ENABLED: Enable/disable tracing (default: False)
    - OTEL_SERVICE_NAME: Service name (default: himalytix-erp)
    - OTEL_EXPORTER: Exporter type (jaeger, otlp, console)
    - JAEGER_HOST: Jaeger agent host (default: localhost)
    - JAEGER_PORT: Jaeger agent port (default: 6831)
    - OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4317)
    """
    
    # Check if tracing is enabled
    if not os.getenv('OTEL_ENABLED', 'False').lower() == 'true':
        return
    
    # Service information
    service_name = os.getenv('OTEL_SERVICE_NAME', 'himalytix-erp')
    environment = os.getenv('DJANGO_ENV', 'development')
    
    # Create resource with service information
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "deployment.environment": environment,
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporter
    exporter_type = os.getenv('OTEL_EXPORTER', 'jaeger').lower()
    
    if exporter_type == 'jaeger':
        # Jaeger exporter
        jaeger_host = os.getenv('JAEGER_HOST', 'localhost')
        jaeger_port = int(os.getenv('JAEGER_PORT', '6831'))
        
        exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
        )
    elif exporter_type == 'otlp':
        # OTLP exporter (for Jaeger, Zipkin, or other OTLP-compatible backends)
        otlp_endpoint = os.getenv('OTLP_ENDPOINT', 'http://localhost:4317')
        
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    else:
        # Console exporter (for debugging)
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        exporter = ConsoleSpanExporter()
    
    # Add span processor
    provider.add_span_processor(BatchSpanProcessor(exporter))
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    # Auto-instrument frameworks
    DjangoInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    
    print(f"✅ OpenTelemetry tracing configured: {service_name} → {exporter_type}")


# Call configuration (will be imported in settings.py)
configure_tracing()
