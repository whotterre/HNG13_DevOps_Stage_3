# HNG13 DevOps Stage 3 Task - Blue/Green Deployment with Nginx Auto-Failover

## Overview

This project implements a Blue/Green deployment strategy for a Node.js application using Nginx as a reverse proxy with automatic failover capabilities. The setup uses Docker Compose to orchestrate two identical application instances (Blue and Green) with Nginx configured to automatically switch from the primary to backup instance on failure.

## Architecture

- **Blue Instance** (Primary): Default active service
- **Green Instance** (Backup): Standby service, activated on Blue failure
- **Nginx**: Reverse proxy with health-based failover and retry logic

## Features

- ✅ Automatic failover from Blue to Green on primary failure
- ✅ Zero downtime during failover (requests retry to backup within same client request)
- ✅ Direct access to both instances for chaos testing
- ✅ Fast failure detection (1-5 second timeouts)
- ✅ Header forwarding (`X-App-Pool`, `X-Release-Id`)
- ✅ Environment-based configuration via `.env` file

## Prerequisites

- Docker
- Docker Compose

## Project Structure

```
.
├── docker-compose.yml          # Main orchestration file
├── .env                        # Environment variables
├── nginx/
│   ├── Dockerfile             # Nginx container build file
│   ├── nginx.conf.template    # Nginx configuration template
│   └── x.sh                   # Template substitution script
└── README.md
```

## Environment Variables

Configure the deployment using the `.env` file:

```env
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two
ACTIVE_POOL=blue
RELEASE_ID_BLUE=v1.blue
RELEASE_ID_GREEN=v2.green
PORT=3000
```

### Variable Descriptions

- `BLUE_IMAGE` - Docker image for the Blue instance
- `GREEN_IMAGE` - Docker image for the Green instance
- `ACTIVE_POOL` - Active pool identifier (blue or green)
- `RELEASE_ID_BLUE` - Release identifier for Blue (returned in `X-Release-Id` header)
- `RELEASE_ID_GREEN` - Release identifier for Green (returned in `X-Release-Id` header)
- `PORT` - Application port (default: 3000)

## Service Endpoints

### Main Service (via Nginx)
- **URL**: `http://localhost:8080`
- **Description**: Load-balanced endpoint with automatic failover

### Direct Instance Access
- **Blue**: `http://localhost:8081` (for chaos testing)
- **Green**: `http://localhost:8082` (for chaos testing)

## Available API Endpoints

### GET /version
Returns version information with headers:
```bash
curl -i http://localhost:8080/version
```

**Response Headers**:
- `X-App-Pool`: blue or green
- `X-Release-Id`: Release identifier

### GET /healthz
Health check endpoint:
```bash
curl http://localhost:8080/healthz
```

### POST /chaos/start
Simulate downtime on a specific instance:
```bash
# Trigger chaos on Blue instance
curl -X POST http://localhost:8081/chaos/start?mode=error

# Or use timeout mode
curl -X POST http://localhost:8081/chaos/start?mode=timeout
```

### POST /chaos/stop
End simulated downtime:
```bash
curl -X POST http://localhost:8081/chaos/stop
```

## Deployment

### 1. Clone and Setup

```bash
cd HNG13_DevOps_Stage_2
```

### 2. Configure Environment

Edit `.env` file with your desired configuration.

### 3. Build and Start Services

```powershell
# Build all services
docker-compose build

# Start all services in detached mode
docker-compose up -d
```

### 4. Verify Deployment

```powershell
# Check running containers
docker-compose ps

# Check logs
docker-compose logs nginx
docker-compose logs blue_app
docker-compose logs green_app
```

### 5. Test the Service

```powershell
# Test main endpoint (should return Blue)
curl -i http://localhost:8080/version

# Simulate Blue failure
curl -X POST http://localhost:8081/chaos/start?mode=error

# Test main endpoint again (should now return Green)
curl -i http://localhost:8080/version

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

## Failover Configuration

### Nginx Upstream Settings

```nginx
upstream app_backend {
    server blue_app:3000 max_fails=2 fail_timeout=5s;
    server green_app:3000 backup;
}
```

- **max_fails**: Number of failed attempts before marking server as down
- **fail_timeout**: Time period for max_fails check
- **backup**: Green only receives traffic when Blue is unavailable

### Proxy Settings

```nginx
proxy_connect_timeout 1s;
proxy_send_timeout 3s;
proxy_read_timeout 3s;
proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
proxy_next_upstream_tries 2;
proxy_next_upstream_timeout 10s;
```

- Fast timeouts ensure quick failure detection
- Retry on errors, timeouts, and 5xx responses
- Maximum 2 retry attempts within 10 seconds

## Stopping Services

```powershell
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Troubleshooting

### Nginx container exits immediately

Check nginx logs:
```powershell
docker-compose logs nginx
```

Common issues:
- Configuration syntax errors
- Missing environment variables
- Template substitution failures

### Can't access services

Verify ports are not in use:
```powershell
netstat -ano | findstr :8080
netstat -ano | findstr :8081
netstat -ano | findstr :8082
```

### Failover not working

1. Check nginx configuration:
```powershell
docker-compose exec nginx cat /etc/nginx/nginx.conf
```

2. Monitor logs during chaos test:
```powershell
docker-compose logs -f nginx
```

3. Verify both instances are running:
```powershell
docker-compose ps
```

## Testing Failover Behavior

### Expected Behavior

1. **Normal State**: All requests → Blue instance
   - `X-App-Pool: blue`
   - `X-Release-Id: v1.blue`

2. **After Chaos on Blue**: Automatic failover → Green instance
   - `X-App-Pool: green`
   - `X-Release-Id: v2.green`

3. **Zero Failed Requests**: Client requests succeed even during failover

### Test Script

```powershell
# Test baseline
for ($i=1; $i -le 10; $i++) { 
    curl -s http://localhost:8080/version | Select-String "X-App-Pool"
}

# Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# Test failover (should show green)
for ($i=1; $i -le 10; $i++) { 
    curl -s http://localhost:8080/version | Select-String "X-App-Pool"
}

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

## Observability & Alerts (Stage 3)

This repository includes a lightweight Python "log_watcher" sidecar that tails Nginx access logs from a shared volume, detects failovers and elevated upstream 5xx error rates, and posts alerts to Slack.

Quick start:

1. Copy `.env.example` to `.env` and set `SLACK_WEBHOOK_URL`.
2. Build and start the stack:

```powershell
docker-compose up --build -d
```

3. The watcher will automatically read `/var/log/nginx/access.log` from the `nginx_logs` volume and post alerts to Slack when configured thresholds are breached. See `runbook.md` for operator actions and tuning.


## CI/CD Considerations

The setup is designed to work with automated CI/CD pipelines:

- All configuration via `.env` (no hardcoded values)
- Supports different image tags per environment
- Fast health checks for quick verification
- Deterministic failover behavior

## Additional Resources

- [Nginx Upstream Documentation](http://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [HNG Internship](https://hng.tech/internship)

