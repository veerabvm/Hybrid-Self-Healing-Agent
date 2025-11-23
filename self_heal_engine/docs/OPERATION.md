# Operations Guide

This guide covers deployment, configuration, monitoring, and maintenance of the Self-Healing Engine in production environments.

## Quick Start

### Local Development

```bash
# Clone and setup
git clone <repository-url>
cd self-heal-engine
pip install -e .[dev]

# Run tests
pytest

# Start service
uvicorn self_heal_engine.app:app --reload
```

### Docker Deployment

```bash
# Build image
docker build -t self-heal-engine .

# Run container
docker run -p 8000:8000 -v $(pwd)/data:/app/data self-heal-engine

# Health check
curl http://localhost:8000/health
```

### Production Deployment

```bash
# Using docker-compose
docker-compose up -d

# Or with Kubernetes
kubectl apply -f k8s/
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONPATH` | `src` | Python module path |
| `HEALING_API_URL` | `http://localhost:8000` | API base URL |
| `LLM_PROVIDER` | `mock` | Default LLM provider |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `MAX_CANDIDATES` | `5` | Default max candidates |
| `MODEL_PATH` | `models/ranker.json` | Trained model path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DATA_DIR` | `data/` | Data storage directory |

### Configuration File

Create `config.yaml`:

```yaml
api:
  host: "0.0.0.0"
  port: 8000
  workers: 4

healing:
  max_candidates: 5
  use_llm: false
  llm_provider: "mock"

storage:
  data_dir: "data/"
  snapshots_dir: "data/snapshots/"
  training_file: "data/training.jsonl"

models:
  ranker_path: "models/ranker.json"
  enable_inference: true

logging:
  level: "INFO"
  format: "json"
  file: "logs/self_heal_engine.log"
```

## API Endpoints

### Health Check

```bash
GET /health

Response: {"status": "ok"}
```

### Healing Request

```bash
POST /heal
Content-Type: application/json

{
  "html": "<html>...</html>",
  "original_locator": "#login-btn",
  "locator_type": "css",
  "context": {
    "anchors": ["Login"],
    "visible_text": "Sign In"
  },
  "max_candidates": 5,
  "use_llm": false
}
```

### Confirmation

```bash
POST /confirm
Content-Type: application/json

{
  "request_id": "uuid-string",
  "accepted_index": 0,
  "metadata": {
    "test_session": "regression_001",
    "browser": "chrome"
  }
}
```

## Monitoring

### Health Checks

The service provides built-in health checks:

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health (if implemented)
curl http://localhost:8000/health/detailed
```

### Metrics

Monitor these key metrics:

- **Request Rate**: Requests per second
- **Response Time**: P95 latency
- **Success Rate**: Healing success percentage
- **Candidate Quality**: Average score of top candidates
- **Error Rate**: 5xx error percentage

### Logging

Logs are structured JSON by default:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "INFO",
  "request_id": "uuid-string",
  "message": "Healing completed",
  "candidates_found": 3,
  "top_score": 0.95,
  "duration_ms": 150
}
```

### Dashboards

Set up monitoring dashboards with:

- **Grafana + Prometheus**: For metrics visualization
- **ELK Stack**: For log aggregation and analysis
- **Custom dashboards**: Request patterns, healing effectiveness

## Performance Tuning

### Memory Optimization

```python
# Limit DOM parsing depth
MAX_DOM_DEPTH = 10

# Limit HTML size
MAX_HTML_SIZE = 1024 * 1024  # 1MB

# Cache compiled regex patterns
import re
ANCHOR_PATTERN = re.compile(r'pattern')
```

### Concurrency

```python
# Configure Uvicorn workers
workers = multiprocessing.cpu_count()

# Async processing for I/O bound operations
async def process_llm_request():
    # LLM API calls
    pass
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_selector_validation(selector, html_hash):
    # Cache expensive validations
    pass
```

## Troubleshooting

### Common Issues

#### No Candidates Found

**Symptoms:**
- API returns empty candidates array
- Low healing success rate

**Causes:**
- Invalid HTML input
- Locator format issues
- Missing context information

**Solutions:**
```bash
# Validate HTML
python -c "from self_heal_engine.parser import parse_html; print(parse_html(your_html) is not None)"

# Check locator syntax
# Use browser dev tools to verify selector works
```

#### High Latency

**Symptoms:**
- Response times > 500ms
- CPU usage spikes

**Causes:**
- Large HTML documents
- Complex DOM structures
- LLM provider timeouts

**Solutions:**
- Implement HTML size limits
- Add DOM depth restrictions
- Configure timeouts for external services

#### Memory Leaks

**Symptoms:**
- Increasing memory usage over time
- Out of memory errors

**Causes:**
- BeautifulSoup object retention
- Large HTML document accumulation
- Model object caching issues

**Solutions:**
```python
# Explicit cleanup
del soup
import gc
gc.collect()
```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
export PYTHONPATH=src

# Run with debug
uvicorn self_heal_engine.app:app --log-level debug
```

### Snapshot Analysis

Examine healing snapshots for debugging:

```python
from self_heal_engine.storage import load_snapshot

snapshot = load_snapshot("request-id")
print(snapshot["candidates"])
print(snapshot["page_html"][:500])  # First 500 chars
```

## Training & Model Management

### Training Pipeline

```bash
# Collect training data
# Service automatically collects via /confirm endpoint

# View statistics
python -c "
from self_heal_engine.storage import get_training_stats
stats = get_training_stats()
print(f'Total records: {stats[\"total_records\"]}')
print(f'Acceptance rate: {stats[\"acceptance_rate\"]:.2%}')
"

# Train model
python -m self_heal_engine.train_ranker

# Validate model
python -c "
from self_heal_engine.train_ranker import validate_model
results = validate_model()
print(f'Accuracy: {results[\"accuracy\"]:.3f}')
"
```

### Model Deployment

```bash
# Backup current model
cp models/ranker.json models/ranker.json.backup

# Deploy new model
cp new_model.json models/ranker.json

# Restart service
docker-compose restart api

# Monitor performance
# Check that healing quality doesn't degrade
```

### A/B Testing

Implement model A/B testing:

```python
# In app.py
import random

def get_model_version():
    return "A" if random.random() < 0.5 else "B"

# Route requests to different models
# Compare performance metrics
```

## Backup & Recovery

### Data Backup

```bash
# Backup training data
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Backup models
tar -czf models-$(date +%Y%m%d).tar.gz models/
```

### Recovery Procedures

```bash
# Restore from backup
tar -xzf backup-20250115.tar.gz

# Validate data integrity
python -c "
from self_heal_engine.storage import get_training_stats
print('Data integrity check:', get_training_stats())
"

# Restart services
docker-compose down
docker-compose up -d
```

## Security

### Input Validation

```python
# HTML size limits
MAX_HTML_SIZE = 1024 * 1024  # 1MB

def validate_html(html: str) -> bool:
    if len(html) > MAX_HTML_SIZE:
        return False
    # Additional validation logic
    return True
```

### Authentication

For production deployments, add authentication:

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.post("/heal")
async def heal_locator(
    request: HealRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # Validate token
    if not validate_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Invalid token")
    # Proceed with healing
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(_rate_limit_exceeded_handler, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.yml for scaling
version: '3.8'
services:
  api:
    image: self-heal-engine
    deploy:
      replicas: 3
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  redis:
    image: redis:alpine
```

### Load Balancing

```nginx
# nginx.conf
upstream healing_api {
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://healing_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Database Scaling

For high-volume training data:

```python
# Use PostgreSQL instead of JSONL files
from sqlalchemy import create_engine

engine = create_engine("postgresql://user:pass@host:5432/db")

# Migrate existing data
# Implement connection pooling
# Add database migrations
```

## Maintenance Tasks

### Regular Tasks

```bash
# Daily: Clean old snapshots
0 2 * * * /path/to/cleanup_snapshots.sh

# Weekly: Backup data
0 3 * * 0 /path/to/backup.sh

# Monthly: Retrain model
0 4 1 * * /path/to/retrain_model.sh
```

### Monitoring Scripts

```bash
#!/bin/bash
# health_check.sh

response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$response" != "200" ]; then
    echo "Health check failed: $response"
    # Send alert
    curl -X POST -H 'Content-type: application/json' \
         --data '{"text":"Self-Healing Engine health check failed"}' \
         $SLACK_WEBHOOK_URL
fi
```

### Log Rotation

```bash
# logrotate.conf
/app/logs/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 0644 www-data www-data
    postrotate
        docker-compose restart api
    endscript
}
```

## Support & Escalation

### Alert Levels

1. **Warning**: Performance degradation (< 95% success rate)
2. **Critical**: Service unavailable (> 5% error rate)
3. **Emergency**: Data loss or corruption

### Escalation Matrix

- **L1**: On-call engineer (15 minutes)
- **L2**: Senior engineer (1 hour)
- **L3**: Engineering manager (4 hours)

### Runbooks

- [Service Restart Procedure](#)
- [Data Recovery](#)
- [Model Retraining](#)
- [Performance Issues](#)

---

*This operations guide should be updated as the system evolves and new operational patterns emerge.*
