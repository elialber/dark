"""The ``langfuse`` module (goal 043): self-hosted Langfuse plus its Claude Code plugin.

The plan writes the official Docker Compose file of the pinned Langfuse release
(community edition) under ``.dark/langfuse/``, with every image at an exact tag
and every password or secret required from ``.dark/langfuse/.env`` instead of a
default value; an example of that ``.env`` with names only; the line that keeps
the ``.env`` out of git; and, in the project's ``.claude/settings.json``, the
official Langfuse plugin (marketplace pinned to a tag, plugin enabled) and the
local instance's address. The API keys are never written: the plugin reads them
from the environment Claude Code starts in, or from its own keychain prompt.

Contents live here as text so the wheel carries them without package data.

Indicator: ``cost_per_task`` (padrão a confirmar). Langfuse records tokens and
cost per turn; it is the first module that sees cost at all.

``verify`` only reads: no network, no Docker, and it never shows a value.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import textfile
from .engine import load_manifest
from .module import Check, Module
from .operations import AppendLine, CreateFile, JsonEntry, Plan

VERSION = "4.82.0"
SOURCE = f"https://github.com/langfuse/langfuse/blob/v{VERSION}/docker-compose.yml"

PLUGIN = "langfuse-observability@langfuse-observability"
PLUGIN_MARKETPLACE = "langfuse-observability"
PLUGIN_REPO = "langfuse/claude-observability-plugin"
PLUGIN_VERSION = "v1.2.2"
# The plugin's fallback without uv: python3 with the SDK inside its range (>=4.7,<5).
SDK_PIN = "langfuse==4.18.0"
BASE_URL = "http://localhost:3000"

DIR = ".dark/langfuse"
COMPOSE_PATH = f"{DIR}/docker-compose.yml"
ENV_EXAMPLE_PATH = f"{DIR}/env.exemplo"
ENV_PATH = f"{DIR}/.env"
SETTINGS_PATH = ".claude/settings.json"

# Required by the compose file, from .dark/langfuse/.env (or the shell).
COMPOSE_SECRETS = (
    "POSTGRES_PASSWORD", "SALT", "ENCRYPTION_KEY", "NEXTAUTH_SECRET",
    "CLICKHOUSE_PASSWORD", "REDIS_AUTH", "MINIO_ROOT_PASSWORD",
)
# Read by the plugin's hook from the environment Claude Code runs in.
INTEGRATION_VARS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")

_MIT_NOTICE = """\
# Copyright (c) 2023-2026 ClickHouse, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""

_COMPOSE_HEADER = f"""\
# Langfuse auto-hospedado: arquivo do módulo langfuse do dark.
# Origem: {SOURCE}
# Versão: Langfuse v{VERSION} (edição community, open source).
# Licença do original: MIT (Expat), aviso completo abaixo.
# Mudanças em relação ao original:
# - toda imagem em etiqueta exata; o MinIO, que só publica `latest`, por digest;
# - toda senha e segredo exigidos de .dark/langfuse/.env (${{NOME:?...}}), sem
#   valor padrão; os segredos do S3 usam MINIO_ROOT_PASSWORD e DATABASE_URL usa
#   POSTGRES_PASSWORD; sem os comentários CHANGEME, que não se aplicam mais.
# Subir: docker compose -f {COMPOSE_PATH} --env-file {ENV_PATH} up -d
#
{_MIT_NOTICE}
"""

_COMPOSE_BODY = """\
# In addition, we recommend to restrict inbound traffic on the host to langfuse-web (port 3000), minio (port 9090)
# and langfuse-ai-gateway (port 3031, or LANGFUSE_AI_GATEWAY_PORT) only.
# LANGFUSE_IMAGE_TAG pins langfuse-web, langfuse-worker and langfuse-ai-gateway to the same release, which must be newer than 4.75.0 (older web images hide the gateway even with both keys set).
# All other components are bound to localhost (127.0.0.1) to only accept connections from the local machine.
# External connections from other machines will not be able to reach these services directly.
services:
  langfuse-worker:
    image: docker.langfuse.com/langfuse/langfuse-worker:4.82.0
    restart: always
    depends_on: &langfuse-depends-on
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
      redis:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
    ports:
      - 127.0.0.1:3030:3030
    environment: &langfuse-worker-env
      NEXTAUTH_URL: ${NEXTAUTH_URL:-http://localhost:3000}
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:?defina POSTGRES_PASSWORD em .dark/langfuse/.env}@postgres:5432/postgres
      SALT: ${SALT:?defina SALT em .dark/langfuse/.env}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:?defina ENCRYPTION_KEY em .dark/langfuse/.env}
      TELEMETRY_ENABLED: ${TELEMETRY_ENABLED:-true}
      LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES: ${LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES:-false}
      # Lets the worker reach the web service internally for in-app agent MCP
      # calls without redirecting NEXTAUTH_URL, which also builds links for
      # users. Pair it with LANGFUSE_MCP_ALLOWED_HOSTS on langfuse-web.
      LANGFUSE_MCP_BASE_URL: ${LANGFUSE_MCP_BASE_URL:-}
      LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST: ${LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST:-}
      LANGFUSE_LLM_CONNECTION_WHITELISTED_IPS: ${LANGFUSE_LLM_CONNECTION_WHITELISTED_IPS:-}
      LANGFUSE_LLM_CONNECTION_WHITELISTED_IP_SEGMENTS: ${LANGFUSE_LLM_CONNECTION_WHITELISTED_IP_SEGMENTS:-}
      # Empty defaults leave egress policy unchanged until an operator sets them.
      LANGFUSE_LLM_CONNECTION_ALLOWED_HOSTS: ${LANGFUSE_LLM_CONNECTION_ALLOWED_HOSTS:-}
      LANGFUSE_WEBHOOK_ALLOWED_HOSTS: ${LANGFUSE_WEBHOOK_ALLOWED_HOSTS:-}
      LANGFUSE_BLOB_STORAGE_ENDPOINT_ALLOWED_HOSTS: ${LANGFUSE_BLOB_STORAGE_ENDPOINT_ALLOWED_HOSTS:-}
      LANGFUSE_EXTERNAL_MEDIA_STORAGE_ENDPOINT_ALLOWED_HOSTS: ${LANGFUSE_EXTERNAL_MEDIA_STORAGE_ENDPOINT_ALLOWED_HOSTS:-}
      LANGFUSE_OUTBOUND_BLOCKED_IP_SEGMENTS: ${LANGFUSE_OUTBOUND_BLOCKED_IP_SEGMENTS:-}
      CLICKHOUSE_MIGRATION_URL: ${CLICKHOUSE_MIGRATION_URL:-clickhouse://clickhouse:9000}
      CLICKHOUSE_URL: ${CLICKHOUSE_URL:-http://clickhouse:8123}
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:?defina CLICKHOUSE_PASSWORD em .dark/langfuse/.env}
      CLICKHOUSE_CLUSTER_ENABLED: ${CLICKHOUSE_CLUSTER_ENABLED:-false}
      CLICKHOUSE_CLUSTER_NAME: ${CLICKHOUSE_CLUSTER_NAME:-default}
      LANGFUSE_JSON_BAD_UNICODE_ESCAPE: ${LANGFUSE_JSON_BAD_UNICODE_ESCAPE:-}
      LANGFUSE_USE_AZURE_BLOB: ${LANGFUSE_USE_AZURE_BLOB:-false}
      LANGFUSE_USE_OCI_NATIVE_OBJECT_STORAGE: ${LANGFUSE_USE_OCI_NATIVE_OBJECT_STORAGE:-false}
      LANGFUSE_OCI_AUTH_TYPE: ${LANGFUSE_OCI_AUTH_TYPE:-workload_identity}
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: ${LANGFUSE_S3_EVENT_UPLOAD_BUCKET:-langfuse}
      LANGFUSE_S3_EVENT_UPLOAD_REGION: ${LANGFUSE_S3_EVENT_UPLOAD_REGION:-auto}
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD:?defina MINIO_ROOT_PASSWORD em .dark/langfuse/.env}
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: ${LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT:-http://minio:9000}
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: ${LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE:-true}
      LANGFUSE_S3_EVENT_UPLOAD_PREFIX: ${LANGFUSE_S3_EVENT_UPLOAD_PREFIX:-events/}
      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: ${LANGFUSE_S3_MEDIA_UPLOAD_BUCKET:-langfuse}
      LANGFUSE_S3_MEDIA_UPLOAD_REGION: ${LANGFUSE_S3_MEDIA_UPLOAD_REGION:-auto}
      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: ${LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD:?defina MINIO_ROOT_PASSWORD em .dark/langfuse/.env}
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: ${LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT:-http://minio:9000}
      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: ${LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE:-true}
      LANGFUSE_S3_MEDIA_UPLOAD_PREFIX: ${LANGFUSE_S3_MEDIA_UPLOAD_PREFIX:-media/}
      LANGFUSE_S3_MEDIA_UPLOAD_REQUEST_TIMEOUT_MS: ${LANGFUSE_S3_MEDIA_UPLOAD_REQUEST_TIMEOUT_MS:-30000}
      LANGFUSE_OBSERVATION_FIELD_OVERFLOW_ENABLED: ${LANGFUSE_OBSERVATION_FIELD_OVERFLOW_ENABLED:-false}
      LANGFUSE_OBSERVATION_FIELD_SIZE_LIMIT_BYTES: ${LANGFUSE_OBSERVATION_FIELD_SIZE_LIMIT_BYTES:-2097152}
      LANGFUSE_S3_BATCH_EXPORT_ENABLED: ${LANGFUSE_S3_BATCH_EXPORT_ENABLED:-false}
      LANGFUSE_S3_BATCH_EXPORT_BUCKET: ${LANGFUSE_S3_BATCH_EXPORT_BUCKET:-langfuse}
      LANGFUSE_S3_BATCH_EXPORT_PREFIX: ${LANGFUSE_S3_BATCH_EXPORT_PREFIX:-exports/}
      LANGFUSE_S3_BATCH_EXPORT_REGION: ${LANGFUSE_S3_BATCH_EXPORT_REGION:-auto}
      LANGFUSE_S3_BATCH_EXPORT_ENDPOINT: ${LANGFUSE_S3_BATCH_EXPORT_ENDPOINT:-http://minio:9000}
      LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT: ${LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT:-http://localhost:9090}
      LANGFUSE_S3_BATCH_EXPORT_ACCESS_KEY_ID: ${LANGFUSE_S3_BATCH_EXPORT_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD:?defina MINIO_ROOT_PASSWORD em .dark/langfuse/.env}
      LANGFUSE_S3_BATCH_EXPORT_FORCE_PATH_STYLE: ${LANGFUSE_S3_BATCH_EXPORT_FORCE_PATH_STYLE:-true}
      LANGFUSE_INGESTION_QUEUE_DELAY_MS: ${LANGFUSE_INGESTION_QUEUE_DELAY_MS:-}
      LANGFUSE_INGESTION_CLICKHOUSE_WRITE_INTERVAL_MS: ${LANGFUSE_INGESTION_CLICKHOUSE_WRITE_INTERVAL_MS:-}
      REDIS_HOST: ${REDIS_HOST:-redis}
      REDIS_PORT: ${REDIS_PORT:-6379}
      REDIS_AUTH: ${REDIS_AUTH:?defina REDIS_AUTH em .dark/langfuse/.env}
      LANGFUSE_BULLMQ_SKIP_REDIS_VERSION_CHECK: ${LANGFUSE_BULLMQ_SKIP_REDIS_VERSION_CHECK:-false}
      REDIS_TLS_ENABLED: ${REDIS_TLS_ENABLED:-false}
      REDIS_TLS_CA: ${REDIS_TLS_CA:-/certs/ca.crt}
      REDIS_TLS_CERT: ${REDIS_TLS_CERT:-/certs/redis.crt}
      REDIS_TLS_KEY: ${REDIS_TLS_KEY:-/certs/redis.key}
      EMAIL_FROM_ADDRESS: ${EMAIL_FROM_ADDRESS:-}
      SMTP_CONNECTION_URL: ${SMTP_CONNECTION_URL:-}
      # Code-based evaluators. Set the dispatcher to "external" to send them to
      # your own executor over HTTP; see .env.prod.example.
      LANGFUSE_CODE_EVAL_DISPATCHER: ${LANGFUSE_CODE_EVAL_DISPATCHER:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_ENDPOINT: ${LANGFUSE_CODE_EVAL_EXTERNAL_ENDPOINT:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_SIGNING_SECRET: ${LANGFUSE_CODE_EVAL_EXTERNAL_SIGNING_SECRET:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_HEADERS: ${LANGFUSE_CODE_EVAL_EXTERNAL_HEADERS:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_TIMEOUT_MS: ${LANGFUSE_CODE_EVAL_EXTERNAL_TIMEOUT_MS:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_CONNECT_TIMEOUT_MS: ${LANGFUSE_CODE_EVAL_EXTERNAL_CONNECT_TIMEOUT_MS:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_MAX_ATTEMPTS: ${LANGFUSE_CODE_EVAL_EXTERNAL_MAX_ATTEMPTS:-}
      LANGFUSE_CODE_EVAL_EXTERNAL_LANGUAGES: ${LANGFUSE_CODE_EVAL_EXTERNAL_LANGUAGES:-}
      # Shared AI features configuration. These apply to AI features that run
      # in both web and worker.
      LANGFUSE_IN_APP_AGENT_ENABLED: ${LANGFUSE_IN_APP_AGENT_ENABLED:-}
      LANGFUSE_EVALUATOR_MEDIA_TRANSPORT: ${LANGFUSE_EVALUATOR_MEDIA_TRANSPORT:-}
      LANGFUSE_EVALUATOR_MEDIA_INLINE_MAX_BYTES: ${LANGFUSE_EVALUATOR_MEDIA_INLINE_MAX_BYTES:-}
      LANGFUSE_AI_PROVIDER: ${LANGFUSE_AI_PROVIDER:-}
      LANGFUSE_AI_MODEL: ${LANGFUSE_AI_MODEL:-}
      LANGFUSE_AI_SMALL_MODEL: ${LANGFUSE_AI_SMALL_MODEL:-}
      LANGFUSE_AI_API_KEY: ${LANGFUSE_AI_API_KEY:-}
      LANGFUSE_AI_BASE_URL: ${LANGFUSE_AI_BASE_URL:-}
      LANGFUSE_AI_USE_RESPONSES_API: ${LANGFUSE_AI_USE_RESPONSES_API:-}
      LANGFUSE_AI_EXTRA_HEADERS: ${LANGFUSE_AI_EXTRA_HEADERS:-}
      LANGFUSE_AI_AWS_BEDROCK_REGION: ${LANGFUSE_AI_AWS_BEDROCK_REGION:-}
      LANGFUSE_AI_VERTEX_LOCATION: ${LANGFUSE_AI_VERTEX_LOCATION:-}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:-}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:-}
      AWS_SESSION_TOKEN: ${AWS_SESSION_TOKEN:-}
      AWS_PROFILE: ${AWS_PROFILE:-}
      LANGFUSE_AI_FEATURES_AWS_PROFILE: ${LANGFUSE_AI_FEATURES_AWS_PROFILE:-}
      LANGFUSE_IN_APP_AGENT_AWS_PROFILE: ${LANGFUSE_IN_APP_AGENT_AWS_PROFILE:-}
      # In-app agent worker settings (ignored by the web service).
      LANGFUSE_IN_APP_AGENT_RUN_QUEUE_PROCESSING_CONCURRENCY: ${LANGFUSE_IN_APP_AGENT_RUN_QUEUE_PROCESSING_CONCURRENCY:-}
      LANGFUSE_IN_APP_AGENT_SANDBOX_PROVIDER: ${LANGFUSE_IN_APP_AGENT_SANDBOX_PROVIDER:-}
      LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_IMAGE_IDENTIFIER: ${LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_IMAGE_IDENTIFIER:-}
      LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_EXECUTION_ROLE_ARN: ${LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_EXECUTION_ROLE_ARN:-}
      LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_EGRESS_NETWORK_CONNECTOR_ARN: ${LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_EGRESS_NETWORK_CONNECTOR_ARN:-}
      LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_REGION: ${LANGFUSE_IN_APP_AGENT_SANDBOX_AWS_LAMBDA_MICROVM_REGION:-}

  langfuse-web:
    image: docker.langfuse.com/langfuse/langfuse:4.82.0
    restart: always
    depends_on: *langfuse-depends-on
    ports:
      - 3000:3000
    environment:
      <<: *langfuse-worker-env
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET:?defina NEXTAUTH_SECRET em .dark/langfuse/.env}
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: ${LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT:-http://localhost:9090}
      LANGFUSE_S3_MEDIA_UPLOAD_INTERNAL_ENDPOINT: ${LANGFUSE_S3_MEDIA_UPLOAD_INTERNAL_ENDPOINT:-http://minio:9000}
      LANGFUSE_INIT_ORG_ID: ${LANGFUSE_INIT_ORG_ID:-}
      LANGFUSE_INIT_ORG_NAME: ${LANGFUSE_INIT_ORG_NAME:-}
      LANGFUSE_INIT_PROJECT_ID: ${LANGFUSE_INIT_PROJECT_ID:-}
      LANGFUSE_INIT_PROJECT_NAME: ${LANGFUSE_INIT_PROJECT_NAME:-}
      LANGFUSE_INIT_PROJECT_PUBLIC_KEY: ${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-}
      LANGFUSE_INIT_PROJECT_SECRET_KEY: ${LANGFUSE_INIT_PROJECT_SECRET_KEY:-}
      LANGFUSE_INIT_USER_EMAIL: ${LANGFUSE_INIT_USER_EMAIL:-}
      LANGFUSE_INIT_USER_NAME: ${LANGFUSE_INIT_USER_NAME:-}
      LANGFUSE_INIT_USER_PASSWORD: ${LANGFUSE_INIT_USER_PASSWORD:-}
      LANGFUSE_MARKDOWN_RENDER_CHARACTER_LIMIT: ${LANGFUSE_MARKDOWN_RENDER_CHARACTER_LIMIT:-}
      LANGFUSE_SKILL_MAX_BYTES: ${LANGFUSE_SKILL_MAX_BYTES:-}
      LANGFUSE_SKILL_MAX_FILES: ${LANGFUSE_SKILL_MAX_FILES:-}
      LANGFUSE_TRUSTED_PROXY_COUNT: ${LANGFUSE_TRUSTED_PROXY_COUNT:-}
      LANGFUSE_DISABLE_SIGNUP_ONBOARDING: ${LANGFUSE_DISABLE_SIGNUP_ONBOARDING:-}
      # Hostnames allowed to reach the MCP endpoint, beyond NEXTAUTH_URL's own
      # host. Required when the worker uses LANGFUSE_MCP_BASE_URL.
      LANGFUSE_MCP_ALLOWED_HOSTS: ${LANGFUSE_MCP_ALLOWED_HOSTS:-}
      # In-app agent settings.
      LANGFUSE_IN_APP_AGENT_MAX_ACTIVE_RUNS_PER_USER: ${LANGFUSE_IN_APP_AGENT_MAX_ACTIVE_RUNS_PER_USER:-}
      LANGFUSE_IN_APP_AGENT_MAX_ACTIVE_RUNS_PER_ORG: ${LANGFUSE_IN_APP_AGENT_MAX_ACTIVE_RUNS_PER_ORG:-}
      # AI gateway: turns on once both keys are set; generate them as described in
      # https://langfuse.com/self-hosting/configuration/ai-gateway
      LANGFUSE_AI_GATEWAY_SERVICE_KEY: ${LANGFUSE_AI_GATEWAY_SERVICE_KEY:-} # same key as langfuse-ai-gateway
      LANGFUSE_AI_GATEWAY_JWT_PRIVATE_KEY: ${LANGFUSE_AI_GATEWAY_JWT_PRIVATE_KEY:-}
      # Key rotation; see "AI gateway control-plane key rotation" in .env.dev.example.
      LANGFUSE_AI_GATEWAY_SERVICE_KEY_PREVIOUS: ${LANGFUSE_AI_GATEWAY_SERVICE_KEY_PREVIOUS:-}
      LANGFUSE_AI_GATEWAY_JWT_KEY_ID: ${LANGFUSE_AI_GATEWAY_JWT_KEY_ID:-}
      LANGFUSE_AI_GATEWAY_JWT_PREVIOUS_KEY_ID: ${LANGFUSE_AI_GATEWAY_JWT_PREVIOUS_KEY_ID:-}
      LANGFUSE_AI_GATEWAY_JWT_PREVIOUS_PUBLIC_KEY: ${LANGFUSE_AI_GATEWAY_JWT_PREVIOUS_PUBLIC_KEY:-}
      # Gateway address shown to users. The default only works on this machine; set it to the
      # gateway's public address when users reach Langfuse from elsewhere.
      LANGFUSE_AI_GATEWAY_PUBLIC_URL: ${LANGFUSE_AI_GATEWAY_PUBLIC_URL:-http://localhost:${LANGFUSE_AI_GATEWAY_PORT:-3031}}
      # Optional: true/false overrides the key-based detection; ENABLED=false limits
      # the gateway to the comma-separated organization IDs in the allowlist.
      LANGFUSE_AI_GATEWAY_DEPLOYED: ${LANGFUSE_AI_GATEWAY_DEPLOYED:-}
      LANGFUSE_AI_GATEWAY_ENABLED: ${LANGFUSE_AI_GATEWAY_ENABLED:-}
      LANGFUSE_AI_GATEWAY_ORGANIZATION_ID_ALLOWLIST: ${LANGFUSE_AI_GATEWAY_ORGANIZATION_ID_ALLOWLIST:-}

  langfuse-ai-gateway:
    # LANGFUSE_AI_GATEWAY_IMAGE_TAG overrides the shared tag, e.g. if a release lacks a gateway image.
    image: docker.langfuse.com/langfuse/ai-gateway:4.82.0
    restart: always
    depends_on:
      - langfuse-web
    ports:
      # LANGFUSE_AI_GATEWAY_PORT (a port number) sets the port inside the container and on the host.
      - ${LANGFUSE_AI_GATEWAY_PORT:-3031}:${LANGFUSE_AI_GATEWAY_PORT:-3031}
    environment:
      # Fixed to the internal service: plain HTTP is allowed only because this address stays
      # on the private Docker network, and Web's responses carry provider API keys.
      # Left empty without a service key, so gateway images that predate
      # LANGFUSE_AI_GATEWAY_ALLOW_MISSING_SERVICE_KEY also start unconfigured.
      LANGFUSE_AI_GATEWAY_WEB_URL: ${LANGFUSE_AI_GATEWAY_SERVICE_KEY:+http://langfuse-web:3000}
      LANGFUSE_AI_GATEWAY_ALLOW_HTTP_WEB_URL: "true"
      LANGFUSE_AI_GATEWAY_LISTEN_ADDRESS: 0.0.0.0:${LANGFUSE_AI_GATEWAY_PORT:-3031}
      # Without the key the gateway starts unconfigured: inference returns 503.
      LANGFUSE_AI_GATEWAY_SERVICE_KEY: ${LANGFUSE_AI_GATEWAY_SERVICE_KEY:-}
      LANGFUSE_AI_GATEWAY_ALLOW_MISSING_SERVICE_KEY: "true"
      LANGFUSE_AI_GATEWAY_CONNECTION_DRAIN_TIMEOUT_SECONDS: ${LANGFUSE_AI_GATEWAY_CONNECTION_DRAIN_TIMEOUT_SECONDS:-30}
      LANGFUSE_AI_GATEWAY_TELEMETRY_SHUTDOWN_TIMEOUT_SECONDS: ${LANGFUSE_AI_GATEWAY_TELEMETRY_SHUTDOWN_TIMEOUT_SECONDS:-20}
      LANGFUSE_LOG_LEVEL: ${LANGFUSE_AI_GATEWAY_LOG_LEVEL:-info}
    # Must exceed the connection drain plus the telemetry flush; raise it with either timeout.
    stop_grace_period: ${LANGFUSE_AI_GATEWAY_STOP_GRACE_PERIOD:-60s}
    healthcheck:
      # Liveness, not /ready: a gateway without keys is unconfigured by design.
      test: ["CMD", "wget", "-qO", "/dev/null", "http://127.0.0.1:${LANGFUSE_AI_GATEWAY_PORT:-3031}/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s

  clickhouse:
    image: docker.io/clickhouse/clickhouse-server:26.3.62.3
    restart: always
    user: "101:101"
    environment:
      CLICKHOUSE_DB: default
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:?defina CLICKHOUSE_PASSWORD em .dark/langfuse/.env}
    volumes:
      - langfuse_clickhouse_data:/var/lib/clickhouse
      - langfuse_clickhouse_logs:/var/log/clickhouse-server
    ports:
      - 127.0.0.1:8123:8123
      - 127.0.0.1:9000:9000
    healthcheck:
      test: wget --no-verbose --tries=1 --spider http://localhost:8123/ping || exit 1
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 1s

  minio:
    image: cgr.dev/chainguard/minio@sha256:7618b82bba99aadd77fcf59eb6cfd89b4b8b8e01ac796c474d57a1c1abf17e79
    restart: always
    entrypoint: sh
    # create the 'langfuse' bucket before starting the service
    command: -c 'mkdir -p /data/langfuse && minio server --address ":9000" --console-address ":9001" /data'
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minio}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:?defina MINIO_ROOT_PASSWORD em .dark/langfuse/.env}
    ports:
      - 9090:9000
      - 127.0.0.1:9091:9001
    volumes:
      - langfuse_minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 1s
      timeout: 5s
      retries: 5
      start_period: 1s

  redis:
    image: docker.io/redis:7.4.12
    restart: always
    command: >
      --requirepass ${REDIS_AUTH:?defina REDIS_AUTH em .dark/langfuse/.env}
      --maxmemory-policy noeviction
    ports:
      - 127.0.0.1:6379:6379
    volumes:
      - langfuse_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 10s
      retries: 10

  postgres:
    image: docker.io/postgres:17.12
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 3s
      timeout: 3s
      retries: 10
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?defina POSTGRES_PASSWORD em .dark/langfuse/.env}
      POSTGRES_DB: ${POSTGRES_DB:-postgres}
      TZ: UTC
      PGTZ: UTC
    ports:
      - 127.0.0.1:5432:5432
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data

volumes:
  langfuse_postgres_data:
    driver: local
  langfuse_clickhouse_data:
    driver: local
  langfuse_clickhouse_logs:
    driver: local
  langfuse_minio_data:
    driver: local
  langfuse_redis_data:
    driver: local
"""

COMPOSE = _COMPOSE_HEADER + _COMPOSE_BODY

_ENV_HELP = {
    "POSTGRES_PASSWORD": "Senha do Postgres (entra também na DATABASE_URL). "
                         "Gere com: openssl rand -hex 32",
    "SALT": "Sal dos hashes das chaves de API. Gere com: openssl rand -hex 32",
    "ENCRYPTION_KEY": "Chave de criptografia, 64 caracteres hexadecimais. "
                      "Gere com: openssl rand -hex 32",
    "NEXTAUTH_SECRET": "Segredo das sessões da interface web. Gere com: openssl rand -hex 32",
    "CLICKHOUSE_PASSWORD": "Senha do ClickHouse. Gere com: openssl rand -hex 32",
    "REDIS_AUTH": "Senha do Redis. Gere com: openssl rand -hex 32",
    "MINIO_ROOT_PASSWORD": "Senha do MinIO (também a chave secreta do S3). "
                           "Gere com: openssl rand -hex 32",
}

ENV_EXAMPLE = f"""\
# Variáveis do Langfuse auto-hospedado: arquivo do módulo langfuse do dark.
# Origem dos nomes: {SOURCE}
# Versão: Langfuse v{VERSION}. Licença do original: MIT (Expat).
# Copie para {ENV_PATH} (o git o ignora) e preencha cada valor:
#   cp {ENV_EXAMPLE_PATH} {ENV_PATH}
# Este exemplo não leva valor nenhum. Nunca versione o .env.
""" + "".join(f"\n# {_ENV_HELP[name]}\n{name}=\n" for name in COMPOSE_SECRETS)

_MARKETPLACE = {"source": {"source": "github", "repo": PLUGIN_REPO, "ref": PLUGIN_VERSION}}

REASONS = {
    COMPOSE_PATH: f"compose oficial do Langfuse v{VERSION}, imagens fixas, segredos do .env",
    ENV_EXAMPLE_PATH: "nomes das variáveis do .env, sem valor, com como gerar cada uma",
    ".gitignore": f"o {ENV_PATH} com os segredos fica fora do git",
    SETTINGS_PATH: f"plugin oficial {PLUGIN} {PLUGIN_VERSION} e endereço da instância local",
}

NOTES = (
    "Depois de aplicar:",
    "  1. Crie o .env da instância (o git o ignora) e preencha cada valor; o comentário",
    "     de cada variável diz como gerá-la:",
    f"       cp {ENV_EXAMPLE_PATH} {ENV_PATH}",
    "  2. Suba a instância (precisa de Docker):",
    f"       docker compose -f {COMPOSE_PATH} --env-file {ENV_PATH} up -d",
    f"     A interface fica em {BASE_URL}; crie lá um projeto e as chaves de API.",
    f"  3. Ao abrir o projeto, o Claude Code oferece o plugin {PLUGIN} {PLUGIN_VERSION}.",
    "     As chaves vão no ambiente de onde o Claude Code é aberto, nunca no",
    f"     {SETTINGS_PATH}, que é versionado: " + " e ".join(INTEGRATION_VARS) + ".",
    f"     Alternativa: /plugin configure {PLUGIN} (a secreta fica no chaveiro do sistema).",
    "  4. O gancho do plugin roda com uv no PATH; sem uv, com python3 3.10 ou mais novo e",
    f"     pip install \"{SDK_PIN}\" (o plugin exige langfuse>=4.7,<5). O dark não instala.",
    "Privacidade: o Langfuse guarda o conteúdo das conversas (pedidos, respostas, entradas e",
    "saídas de ferramentas) na sua instância. O dark não guarda conteúdo de conversas, só",
    "agregados; ver \"Guardar conteúdo de conversas\" em docs/visao.md.",
)


def _operations() -> tuple:
    return (
        CreateFile(COMPOSE_PATH, COMPOSE),
        CreateFile(ENV_EXAMPLE_PATH, ENV_EXAMPLE),
        AppendLine(".gitignore", ENV_PATH),
        JsonEntry(SETTINGS_PATH, ("extraKnownMarketplaces",), PLUGIN_MARKETPLACE, _MARKETPLACE),
        JsonEntry(SETTINGS_PATH, ("enabledPlugins",), PLUGIN, True),
        JsonEntry(SETTINGS_PATH, ("env",), "LANGFUSE_BASE_URL", BASE_URL),
    )


def _declared_names(env_file: Path) -> set[str]:
    """Names given a non-empty value in a dotenv file. Values are not kept."""
    try:
        text = env_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    names = set()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, rest = line.partition("=")
        if sep and not line.startswith("#") and rest.strip().strip("\"'"):
            names.add(name.strip())
    return names


def _settings_problem(repo: Path) -> str | None:
    try:
        data = json.loads((repo / SETTINGS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"{SETTINGS_PATH} ausente ou ilegível"
    if not isinstance(data, dict):
        return f"{SETTINGS_PATH} não é um objeto JSON"
    plugins = data.get("enabledPlugins")
    markets = data.get("extraKnownMarketplaces")
    env = data.get("env")
    if not (isinstance(plugins, dict) and plugins.get(PLUGIN) is True
            and isinstance(markets, dict) and markets.get(PLUGIN_MARKETPLACE) == _MARKETPLACE
            and isinstance(env, dict) and env.get("LANGFUSE_BASE_URL")):
        return f"ligação com o Claude Code ausente em {SETTINGS_PATH}"
    return None


class Langfuse(Module):
    name = "langfuse"
    version = VERSION
    indicator = "cost_per_task"
    reasons = REASONS
    notes = NOTES

    def plan(self, repo: Path) -> Plan:
        return Plan(self.name, self.version, _operations())

    def verify(self, repo: Path) -> Check:
        repo = Path(repo)
        if not any(e.get("module") == self.name for e in load_manifest(repo)["entries"]):
            return Check(False, "o módulo não foi aplicado")
        problems = []
        for path, content in ((COMPOSE_PATH, COMPOSE), (ENV_EXAMPLE_PATH, ENV_EXAMPLE)):
            try:
                same = textfile.same_bytes((repo / path).read_bytes(), content.encode("utf-8"))
            except OSError:
                problems.append(f"ausente: {path}")
                continue
            if not same:
                problems.append(f"diferente do aplicado: {path}")
        try:
            ignored = (repo / ".gitignore").read_text(encoding="utf-8", errors="replace")
        except OSError:
            ignored = ""
        if ENV_PATH not in [line.strip() for line in ignored.splitlines()]:
            problems.append(f".gitignore sem a linha {ENV_PATH}")
        wiring = _settings_problem(repo)
        if wiring:
            problems.append(wiring)
        in_file = _declared_names(repo / ENV_PATH)
        missing = [n for n in COMPOSE_SECRETS if not os.environ.get(n) and n not in in_file]
        missing += [n for n in INTEGRATION_VARS if not os.environ.get(n)]
        if missing:
            problems.append("variáveis ausentes: " + ", ".join(missing))
        return Check(not problems, "; ".join(problems))
