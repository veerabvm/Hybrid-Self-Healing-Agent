# Self-Healing Engine

A production-ready AI-powered web element locator healing service that automatically generates robust CSS/XPath selectors when original locators fail due to DOM changes.

## Features

- **Multiple Healing Strategies**: Data-test attributes, ID/name matching, fuzzy token similarity, visible text correlation, and more
- **DOM Hierarchy Search**: Anchor-based and neighbor locality search for moved elements
- **LLM Integration**: Pluggable LLM adapters (OpenAI, APEX, local models) for advanced healing
- **Feature-Based Ranking**: Machine learning-powered candidate ranking and scoring
- **Safety & Verification**: Destructive action detection and automated verification
- **Training Pipeline**: Collect healing data and train custom ranking models
- **REST API**: FastAPI-based service with comprehensive endpoints

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/veerabvm/Hybrid-Self-Healing-Agent.git
cd self-heal-engine

# Install dependencies
pip install -e .[dev]

# Run tests
pytest

# Start the service
uvicorn self_heal_engine.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Build and run with Docker
docker build -t self-heal-engine .
docker run -p 8000:8000 self-heal-engine
```

## API Usage

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### Heal a Locator

```bash
curl -X POST http://localhost:8000/heal \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<html><body><button id=\"login\">Login</button></body></html>",
    "original_locator": "#old-login-btn",
    "locator_type": "css",
    "context": {
      "anchors": ["Login"],
      "visible_text": "Login"
    },
    "max_candidates": 5
  }'
```

Response:
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "candidates": [
    {
      "locator": "#login",
      "type": "css",
      "score": 0.95,
      "reason": "id exact match",
      "features": {...}
    }
  ],
  "auto_apply_index": 0,
  "verify_action": {
    "type": "exists",
    "locator": "#login",
    "locator_type": "css",
    "details": {...}
  }
}
```

### Confirm Healing

```bash
curl -X POST http://localhost:8000/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "accepted_index": 0,
    "metadata": {
      "test_session": "regression_test_001",
      "browser": "chrome"
    }
  }'
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Driver    │───▶│  Self-Heal API   │───▶│  Healing Engine  │
│   (Selenium)    │    │    (FastAPI)     │    │                 │
└─────────────────┘    └──────────────────┘    │  ┌─────────────┐ │
                                               │  │ Heuristics  │ │
┌─────────────────┐    ┌──────────────────┐    │  │ Engine      │ │
│   Test Runner   │◀───│   Verification   │    │  └─────────────┘ │
│                 │    │                  │    │                  │
└─────────────────┘    └──────────────────┘    │  ┌─────────────┐ │
                                               │  │ Hierarchy   │ │
                                               │  │ Search      │ │
                                               │  └─────────────┘ │
                                               │                  │
                                               │  ┌─────────────┐ │
                                               │  │ LLM Adapter │ │
                                               │  └─────────────┘ │
                                               │                  │
                                               │  ┌─────────────┐ │
                                               │  │ Ranker &    │ │
                                               │  │ Features    │ │
                                               │  └─────────────┘ │
                                               └─────────────────┘
```

## Healing Strategies

### 1. Heuristic Rules
- **Data-test exact match**: `[data-test="login"]`
- **ID exact match**: `#login-button`
- **Name exact match**: `[name="username"]`
- **Class name exact match**: `.btn-primary`
- **CSS selector fallback**: Simplify complex selectors
- **Hyperlink text matching**: Exact and partial text matches
- **Combined similarity**: ID/name/class token overlap

### 2. Hierarchy Search
- **Anchor-based search**: Find stable nearby elements and search their subtrees
- **Neighbor locality**: Use sibling text signatures
- **Subtree similarity**: Jaccard similarity on element content

### 3. LLM Enhancement
- **Mock provider**: Rule-based candidate generation
- **OpenAI/APEX**: GPT-powered locator suggestions
- **Validation**: Ensure LLM suggestions are valid selectors

## Training & Model Improvement

### Collect Training Data

The service automatically collects healing decisions:

```bash
# View training data statistics
python -c "from self_heal_engine.storage import get_training_stats; print(get_training_stats())"
```

### Train Custom Ranker

```bash
# Train a new ranking model
python -m self_heal_engine.train_ranker

# The model will be saved to models/ranker.json
```

### Model Inference

```python
from self_heal_engine.model_inference import RankerModel

ranker = RankerModel()
scored_candidates = ranker.score_candidates_with_model(candidates, soup)
```

## Integration Examples

### Java (Selenium)

See `examples/HealingHelper.java` for a complete Java integration example.

```java
HealingHelper healer = new HealingHelper(driver);
String healedLocator = healer.healLocator("#old-button", "css", context);
if (healedLocator != null) {
    WebElement element = driver.findElement(By.cssSelector(healedLocator));
    element.click();
}
```

### Python (pytest-selenium)

```python
import requests
from selenium import webdriver

def heal_locator(original_locator, context):
    response = requests.post("http://localhost:8000/heal", json={
        "html": driver.page_source,
        "original_locator": original_locator,
        "locator_type": "css",
        "context": context
    })
    return response.json()

# In your test
try:
    driver.find_element(By.CSS_SELECTOR, "#login-btn").click()
except NoSuchElementException:
    result = heal_locator("#login-btn", {"anchors": ["Login"]})
    if result["candidates"]:
        healed_locator = result["candidates"][0]["locator"]
        driver.find_element(By.CSS_SELECTOR, healed_locator).click()
```

## Configuration

### Environment Variables

- `HEALING_API_URL`: API base URL (default: `http://localhost:8000`)
- `LLM_PROVIDER`: Default LLM provider (`mock`, `openai`, `apex`)
- `OPENAI_API_KEY`: OpenAI API key (if using OpenAI provider)
- `MAX_CANDIDATES`: Default maximum candidates (default: 5)
- `MODEL_PATH`: Path to trained ranking model

### LLM Providers

#### Mock (Default)
- Rule-based candidate generation
- No external dependencies
- Good for testing and development

#### OpenAI
```bash
export OPENAI_API_KEY="your-api-key"
# Use provider="openai" in API calls
```

#### APEX
- Custom APEX integration
- Requires APEX credentials and endpoints

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_app.py

# Run with coverage
pytest --cov=self_heal_engine --cov-report=html
```

### Adding New Healing Rules

1. Add your rule function to `heuristics.py`
2. Update the `generate_candidates` function to call your rule
3. Add tests in `test_heuristics.py`
4. Update feature extraction in `ranker.py` if needed

### Training Data Management

```bash
# View training statistics
python -c "from self_heal_engine.storage import get_training_stats; import json; print(json.dumps(get_training_stats(), indent=2))"

# Export training data
python -c "from self_heal_engine.storage import export_training_data; export_training_data('training_export.jsonl')"

# Clean old snapshots
python -c "from self_heal_engine.storage import cleanup_old_snapshots; print(f'Cleaned {cleanup_old_snapshots()} snapshots')"
```

## API Reference

### POST /heal

**Request Body:**
```json
{
  "request_id": "string (required)",
  "test_id": "string",
  "page_url": "string",
  "original_locator": "string (required)",
  "original_locator_type": "id|css|xpath|name|link_text|partial_link_text|class_name|text (required)",
  "action": "click|send_keys|get_text|submit|none|string (required)",
  "page_html": "string (required)",
  "element_outer_html": "string",
  "anchors": ["string"],
  "prev_sibling_text": "string",
  "next_sibling_text": "string",
  "screenshot_base64": "string",
  "user_id": "string",
  "username": "string",
  "pii_masked": true
}
```

**Example Request:**
```json
{
  "request_id": "req-001",
  "test_id": "login_smoke",
  "page_url": "https://app.example.com/login",
  "original_locator": "#loginBtn",
  "original_locator_type": "css",
  "action": "click",
  "page_html": "<html><body><button id=\"loginBtn\">Sign in</button></body></html>",
  "element_outer_html": "<button id=\"loginBtn\">Sign in</button>",
  "anchors": ["Email address", "Password"],
  "prev_sibling_text": "Password",
  "next_sibling_text": "Forgot password?",
  "screenshot_base64": null,
  "user_id": null,
  "username": null,
  "pii_masked": true
}
```

**Response:**
```json
{
  "request_id": "string",
  "healed_locator": {
    "locator": "string",
    "type": "string",
    "score": "number"
  } | null,
  "candidates": [],
  "auto_apply_index": -1,
  "verify_action": null,
  "warning": "string" | null,
  "message": "string"
}
```

**Example Response:**
```json
{
  "request_id": "req-001",
  "healed_locator": {
    "locator": "#loginBtn",
    "type": "css",
    "score": 1.0
  },
  "candidates": [],
  "auto_apply_index": -1,
  "verify_action": null,
  "warning": null,
  "message": "updated API: received payload"
}
```

### POST /confirm

**Request Body:**
```json
{
  "request_id": "string (required)",
  "accepted_index": "number (required)",
  "metadata": "object (optional)"
}
```

## Troubleshooting

### Common Issues

1. **No candidates found**: Check that your HTML is valid and contains the expected elements
2. **Low scoring candidates**: Try providing more context (anchors, sibling text)
3. **LLM provider errors**: Ensure API keys are set for external providers
4. **Model not found**: Train a ranking model or use default scoring

### Debugging

```bash
# Enable debug logging
export PYTHONPATH=src
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from self_heal_engine.app import app
# ... your debugging code
"
```

### Performance Tuning

- **Max candidates**: Lower values improve performance
- **LLM usage**: Disable for faster responses
- **Context provision**: More specific context improves accuracy
- **Model caching**: Keep trained models in memory

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Made with ❤️ for robust test automation**
