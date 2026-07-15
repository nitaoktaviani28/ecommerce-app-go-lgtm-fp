# LGTM Full-Pillar Docker Swarm Stack

Konfigurasi lengkap untuk deployment **Grafana LGTM Stack** (Logs, Grafana, Traces, Metrics + Profiles) di Docker Swarm dengan AI Incident Summary.

## Arsitektur

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Swarm (Azure VM)                   │
├─────────────────────────────────────────────────────────────────┤
│  Application Layer                                               │
│  ┌──────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ Frontend │ │ API Gateway │ │  Product    │ │   Order     │  │
│  │ (Vue.js) │ │   (Go)      │ │  Service    │ │  Service    │  │
│  └──────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐              │
│  │    User     │ │   Payment   │ │  PostgreSQL  │              │
│  │  Service    │ │   Service   │ │              │              │
│  └─────────────┘ └─────────────┘ └──────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Observability Layer (LGTM + Faro + Pyroscope)                   │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────────┐ ┌─────────────┐  │
│  │ Loki  │ │ Mimir │ │ Tempo │ │ Pyroscope │ │    Alloy    │  │
│  │(Logs) │ │(Metr.)│ │(Trace)│ │ (Profile) │ │ (Collector) │  │
│  └───────┘ └───────┘ └───────┘ └───────────┘ └─────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  AI & Alerting Layer                                             │
│  ┌───────────┐ ┌───────────────┐                                │
│  │  Grafana  │ │ Bedrock Proxy │ → AWS Bedrock (Nova Lite)      │
│  │  (UI)     │ │ (AI Summary)  │ → Email (SMTP Gmail)           │
│  └───────────┘ └───────────────┘                                │
├─────────────────────────────────────────────────────────────────┤
│  Storage: Azure Blob Storage (blobstoragelgtmfpv1)               │
└─────────────────────────────────────────────────────────────────┘
```

## Struktur Folder

```
lgtm-fp-docker/
├── docker-compose.swarm.yaml      # Main stack definition
├── bedrock-proxy/                  # AI Incident Summary Service
│   ├── app.py                     # Flask app (OpenAI-compatible + webhook)
│   ├── Dockerfile
│   └── requirements.txt
├── configs/
│   ├── alloy/
│   │   └── alloy-config.alloy     # Telemetry collector config
│   ├── grafana/
│   │   ├── dashboards-json/       # Pre-built dashboards
│   │   │   ├── faro-dashboard.json
│   │   │   └── mimir-infra-dashboard.json
│   │   └── provisioning/
│   │       ├── alerting/
│   │       │   ├── alert-rules.yaml
│   │       │   ├── contact-points.yaml
│   │       │   └── notification-policies.yaml
│   │       ├── dashboards/
│   │       │   └── dashboards.yaml
│   │       └── datasources/
│   │           └── datasources.yaml
│   ├── loki/
│   │   └── loki-config.yaml       # Log storage (Azure Blob)
│   ├── mimir/
│   │   ├── mimir-config.yaml      # Metrics storage (Azure Blob)
│   │   └── alertmanager-fallback.yaml
│   ├── pyroscope/
│   │   └── pyroscope-config.yaml  # Continuous profiling (Azure Blob)
│   └── tempo/
│       └── tempo-config.yaml      # Traces storage (Azure Blob)
└── README.md
```

## Prerequisites

- Docker Swarm initialized (`docker swarm init`)
- Azure VM with 32GB RAM, 8 CPU cores
- Azure Blob Storage account (`blobstoragelgtmfpv1`) with containers:
  - `loki`, `mimir-blocks`, `mimir-alertmanager`, `mimir-ruler`, `tempo-traces`, `pyroscope-data`
- AWS account with Bedrock access (model: `amazon.nova-lite-v1:0`)
- Gmail app password for SMTP alerts

## Deployment

### 1. Build Bedrock Proxy Image

```bash
cd bedrock-proxy
docker build -t bedrock-proxy:latest .
```

### 2. Deploy Stack

```bash
cd lgtm-fp-docker
docker stack deploy -c docker-compose.swarm.yaml ecommerce
```

### 3. Verify Services

```bash
docker service ls
```

Semua services harus running:
| Service | Port | Description |
|---------|------|-------------|
| frontend | 3000 | Vue.js ecommerce app |
| api-gateway | 8080 | Go API gateway |
| grafana | 3001 | Grafana UI |
| loki | 3100 | Log aggregation |
| mimir | 9009 | Metrics (Prometheus-compatible) |
| tempo | 3200 | Distributed tracing |
| pyroscope | 4040 | Continuous profiling |
| alloy | 4317/4318/12347 | OTel collector + Faro |
| bedrock-proxy | 4000 | AI summary webhook |
| postgres | 5432 | Application database |

## Fitur AI Incident Summary

Flow ketika alert terpicu:
1. Grafana evaluates alert rules (CPU > 85%, Memory > 85%, Error Rate > 5%, etc.)
2. Notification policy routes ke 2 receiver:
   - **email-notifications**: Kirim raw alert ke email
   - **ai-incident-summary**: Kirim payload ke bedrock-proxy webhook
3. Bedrock Proxy menerima alert → generate AI summary via AWS Bedrock (Nova Lite)
4. AI summary dikirim sebagai formatted HTML email

## Access

| Service | URL |
|---------|-----|
| Frontend | http://172.188.11.67:3000 |
| Grafana | http://172.188.11.67:3001 (admin/admin) |
| API Gateway | http://172.188.11.67:8080/api |
| Bedrock Proxy Health | http://172.188.11.67:4000/health |

## Alert Rules

| Alert | Threshold | Severity |
|-------|-----------|----------|
| High Node CPU | > 85% for 5m | warning |
| High Node Memory | > 85% for 5m | warning |
| High Node Disk | > 85% for 5m | critical |
| High Error Rate | > 5% for 5m | critical |
| High P95 Latency | > 2s for 5m | warning |
| No Traffic | < 0.001 req/s for 10m | critical |

## Catatan

- Storage backend semua menggunakan **Azure Blob Storage** (retention 72h)
- Mimir multi-tenant enabled (tenant: `docker-swarm`)
- Alloy deployed in **global mode** (1 instance per node)
- Bedrock Proxy lightweight (~50MB RAM, replaces LiteLLM yang OOM 2GB+)
