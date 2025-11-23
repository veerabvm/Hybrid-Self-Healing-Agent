# Architecture Overview

## System Architecture

The Self-Healing Engine is a microservice designed to automatically repair broken web element locators in automated test suites. It combines multiple healing strategies with machine learning-powered ranking to provide robust, context-aware locator suggestions.

```
┌─────────────────────────────────────────────────────────────┐
│                    Self-Healing Engine                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                REST API Layer                     │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │    │
│  │  │  /heal  │  │ /confirm│  │ /health │            │    │
│  │  └─────────┘  └─────────┘  └─────────┘            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Core Healing Engine                  │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────┐   │    │
│  │  │Heuristics│  │Hierarchy│  │  LLM   │  │Ranker│   │    │
│  │  │ Engine   │  │ Search  │  │Adapter │  │      │   │    │
│  │  └─────────┘  └─────────┘  └────────┘  └──────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            Training & Learning                     │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │    │
│  │  │Training │  │Model    │  │Storage  │            │    │
│  │  │Pipeline │  │Inference│  │         │            │    │
│  │  └─────────┘  └─────────┘  └─────────┘            │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. REST API Layer (FastAPI)

**Endpoints:**
- `GET /health` - Health check
- `POST /heal` - Main healing orchestration
- `POST /confirm` - Training data collection

**Responsibilities:**
- Request validation and serialization
- Orchestration of healing pipeline
- Response formatting
- Error handling

### 2. Core Healing Engine

#### Heuristics Engine
**Strategies:**
- Data-test attribute matching
- ID, name, class exact matches
- Tokenized fuzzy matching
- Visible text similarity
- CSS selector simplification
- Hyperlink text matching

#### Hierarchy Search
**Capabilities:**
- Anchor-based subtree exploration
- Neighbor locality search
- Subtree similarity comparison
- Path relaxation/CSS trimming
- Depth-based scoring

#### LLM Adapter
**Providers:**
- Mock (rule-based fallback)
- OpenAI GPT integration
- APEX custom integration
- Local model support

#### Ranker & Features
**Feature Extraction:**
- Uniqueness count
- DOM depth
- Visibility status
- Text/attribute similarity
- Structural complexity
- Anchor proximity

### 3. Training & Learning

#### Training Pipeline
- Data collection from healing decisions
- Feature engineering
- LightGBM model training
- Model validation and deployment

#### Model Inference
- Real-time candidate scoring
- A/B testing support
- Model versioning

#### Storage
- Training data persistence (JSONL)
- Snapshot management
- Model artifact storage

## Data Flow

### Healing Request Flow

```
1. Client Request
       ↓
2. HTML Parsing & Validation
       ↓
3. Parallel Strategy Execution
   ┌─────────────────┬─────────────────┬─────────────────┐
   │   Heuristics    │   Hierarchy     │      LLM        │
   │   Engine        │   Search        │   Adapter       │
   └─────────────────┴─────────────────┴─────────────────┘
                           ↓
4. Candidate Aggregation
                           ↓
5. Feature Extraction & Ranking
                           ↓
6. Safety & Verification Checks
                           ↓
7. Response Generation
                           ↓
8. Background Snapshot Storage
```

### Training Data Flow

```
User Feedback → Confirmation API → Training Record → JSONL Storage
                                                            ↓
Feature Engineering → LightGBM Training → Model Validation → Deployment
                                                            ↓
Model Registry → Inference Service → Improved Rankings
```

## Design Principles

### 1. Modularity
- Pluggable components (LLM adapters, rankers)
- Clear separation of concerns
- Interface-based design

### 2. Performance
- Asynchronous processing where possible
- Efficient DOM parsing and traversal
- Caching and memoization
- Configurable limits and timeouts

### 3. Reliability
- Comprehensive error handling
- Graceful degradation (fallback strategies)
- Input validation and sanitization
- Health monitoring and metrics

### 4. Extensibility
- Plugin architecture for new strategies
- Configuration-driven behavior
- API versioning support

### 5. Observability
- Structured logging
- Performance metrics
- Request tracing
- Debug snapshots

## Technology Choices

### Core Framework
- **FastAPI**: High-performance async API framework
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for production deployment

### Data Processing
- **BeautifulSoup + lxml**: Robust HTML parsing and manipulation
- **LightGBM**: Efficient gradient boosting for ranking
- **pandas**: Data manipulation for training

### Infrastructure
- **Docker**: Containerization for consistent deployment
- **GitHub Actions**: CI/CD pipeline
- **pytest**: Comprehensive testing framework

## Scalability Considerations

### Horizontal Scaling
- Stateless API design
- External storage for training data
- Model versioning for A/B testing

### Performance Optimization
- DOM parsing optimization
- Feature extraction caching
- Batch processing for training

### Resource Management
- Memory-efficient DOM processing
- Configurable concurrency limits
- Automatic cleanup of old snapshots

## Security Considerations

### Input Validation
- HTML sanitization and size limits
- Locator format validation
- Context data filtering

### Safe Execution
- Destructive action detection
- Sandboxed LLM execution
- Rate limiting and abuse prevention

### Data Privacy
- PII masking in HTML content
- Secure credential handling
- Audit logging for compliance

## Deployment Architecture

### Development
```
┌─────────────┐    ┌─────────────┐
│ Local Dev   │────│ pytest      │
│ Environment │    │ Coverage    │
└─────────────┘    └─────────────┘
```

### Staging
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Docker      │────│ Integration │────│ E2E Tests   │
│ Container   │    │ Tests       │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Production
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Load        │────│ API Service │────│ PostgreSQL  │
│ Balancer    │    │ (k8s)       │    │ Training DB │
└─────────────┘    └─────────────┘    └─────────────┘
        │                    │              │
        └────────────────────┼──────────────┘
                             │
                    ┌─────────────┐
                    │ Model       │
                    │ Registry    │
                    │ (S3/MinIO)  │
                    └─────────────┘
```

## Monitoring & Observability

### Metrics
- Request latency and throughput
- Healing success rates by strategy
- Model performance metrics
- Error rates and types

### Logging
- Structured JSON logs
- Request/response tracing
- Error context and stack traces
- Performance profiling

### Alerting
- Service health checks
- Performance degradation
- High error rates
- Model accuracy drift

## Future Enhancements

### Advanced Features
- Visual element recognition
- Multi-modal healing (images + DOM)
- Cross-browser compatibility
- Mobile app support

### AI/ML Improvements
- Deep learning for element recognition
- Reinforcement learning for strategy selection
- Ensemble methods for ranking
- Automated feature engineering

### Platform Integration
- Native Selenium plugin
- Cypress integration
- Playwright support
- Appium mobile testing

### Enterprise Features
- Multi-tenant isolation
- Advanced access controls
- Audit trails and compliance
- High availability deployment
