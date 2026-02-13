"""Prometheus metrics for deployment mode monitoring."""

from prometheus_client import Counter, Gauge

# Deployment mode info gauge
DEPLOYMENT_MODE_INFO = Gauge(
    'registry_deployment_mode_info',
    'Current deployment mode configuration',
    ['deployment_mode', 'registry_mode']
)

# Counter for skipped nginx updates
NGINX_UPDATES_SKIPPED = Counter(
    'registry_nginx_updates_skipped_total',
    'Number of nginx updates skipped due to registry-only mode',
    ['operation']  # generate_config, reload
)
