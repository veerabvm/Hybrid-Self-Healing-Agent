# APEX Integration Guide

This guide explains how to integrate the Self-Healing Engine with the APEX test automation platform.

## Overview

The Self-Healing Engine provides robust locator healing capabilities that can be seamlessly integrated into APEX workflows. This integration allows APEX tests to automatically recover from UI changes without manual intervention.

## Integration Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     APEX        │────│  Self-Healing    │────│   Web Driver    │
│   Test Runner   │    │     Engine       │    │   (Selenium)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Test Scripts   │    │   REST API       │    │   Browser       │
│                 │    │   Calls          │    │   Automation    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Setup

### 1. Deploy Self-Healing Engine

```bash
# Using Docker
docker run -d -p 8000:8000 --name healing-engine \
  -v /path/to/data:/app/data \
  ghcr.io/your-org/self-heal-engine:latest

# Verify deployment
curl http://localhost:8000/health
```

### 2. Configure APEX

Update your APEX configuration:

```json
{
  "healing": {
    "enabled": true,
    "api_url": "http://localhost:8000",
    "timeout": 5000,
    "max_candidates": 3,
    "auto_apply": true
  }
}
```

### 3. Environment Variables

```bash
export APEX_HEALING_ENABLED=true
export APEX_HEALING_API_URL=http://localhost:8000
export APEX_HEALING_TIMEOUT=5000
```

## APEX Integration Points

### 1. Element Location Hook

Integrate healing into APEX's element location mechanism:

```java
// In APEX ElementLocator class
public WebElement findElement(By locator) {
    try {
        return driver.findElement(locator);
    } catch (NoSuchElementException e) {
        // Attempt healing
        HealingResult result = healingService.heal(locator, driver.getPageSource());
        if (result.hasCandidates()) {
            By healedLocator = result.getTopCandidate().toSeleniumBy();
            return driver.findElement(healedLocator);
        }
        throw e; // Re-throw if healing fails
    }
}
```

### 2. Test Execution Integration

Modify APEX test execution to include healing:

```java
// In APEX TestExecutor
public void executeTest(TestCase testCase) {
    try {
        // Normal test execution
        runTestSteps(testCase);
    } catch (ElementNotFoundException e) {
        HealingContext context = buildHealingContext(e);
        HealingResult result = healingService.heal(context);

        if (result.shouldAutoApply()) {
            // Update test case with healed locator
            updateTestLocator(testCase, result.getTopCandidate());
            // Retry test execution
            runTestSteps(testCase);
        } else {
            // Log healing suggestions
            logHealingSuggestions(result);
            throw e;
        }
    }
}
```

### 3. Result Reporting

Integrate healing results into APEX reporting:

```java
// In APEX TestReporter
public void reportTestResult(TestResult result) {
    if (result.hasHealingApplied()) {
        // Add healing information to report
        report.addSection("Locator Healing", buildHealingReport(result));
    }
    // Generate standard report
    generateReport(result);
}
```

## API Usage in APEX

### Basic Healing Request

```java
public HealingResult healLocator(String originalLocator, String locatorType) {
    String pageHtml = driver.getPageSource();
    Map<String, Object> context = buildContext(driver);

    // Prepare request
    Map<String, Object> request = Map.of(
        "html", pageHtml,
        "original_locator", originalLocator,
        "locator_type", locatorType,
        "context", context,
        "max_candidates", 3
    );

    // Call healing API
    HttpResponse<String> response = httpClient.send(
        HttpRequest.newBuilder()
            .uri(URI.create(healingApiUrl + "/heal"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(
                objectMapper.writeValueAsString(request)))
            .build(),
        HttpResponse.BodyHandlers.ofString()
    );

    return objectMapper.readValue(response.body(), HealingResult.class);
}
```

### Context Building

```java
private Map<String, Object> buildContext(WebDriver driver) {
    Map<String, Object> context = new HashMap<>();

    try {
        // Get visible text near the failed element
        // This requires additional logic to identify the intended element area
        context.put("visible_text", extractVisibleText(driver));

        // Find anchor elements (headings, labels, etc.)
        List<String> anchors = findAnchorElements(driver);
        context.put("anchors", anchors);

        // Get sibling text if available
        String siblingText = findSiblingText(driver);
        if (siblingText != null) {
            context.put("prev_sibling_text", siblingText);
        }

    } catch (Exception e) {
        // Context building failed, continue with empty context
    }

    return context;
}
```

### Result Processing

```java
public void processHealingResult(HealingResult result, TestCase testCase) {
    if (!result.getCandidates().isEmpty()) {
        Candidate topCandidate = result.getCandidates().get(0);

        // Log healing attempt
        logger.info("Healed locator: {} -> {} (score: {})",
            result.getOriginalLocator(),
            topCandidate.getLocator(),
            topCandidate.getScore());

        // Update test case if auto-apply is enabled
        if (result.getAutoApplyIndex() >= 0) {
            updateTestCaseLocator(testCase, topCandidate);
        }

        // Send confirmation to improve future healing
        confirmHealing(result.getRequestId(), result.getAutoApplyIndex());
    }
}
```

## Advanced Integration Features

### 1. Batch Healing

For scenarios with multiple locator failures:

```java
public List<HealingResult> healBatch(List<FailedLocator> failures) {
    List<CompletableFuture<HealingResult>> futures = failures.stream()
        .map(failure -> CompletableFuture.supplyAsync(() ->
            healLocator(failure.getLocator(), failure.getType())))
        .collect(Collectors.toList());

    return futures.stream()
        .map(CompletableFuture::join)
        .collect(Collectors.toList());
}
```

### 2. Learning Integration

Feed APEX test results back to improve healing:

```java
public void integrateTestResults(TestExecutionResult result) {
    for (TestStepResult step : result.getStepResults()) {
        if (step.isHealed()) {
            // Send confirmation with test context
            confirmHealing(step.getHealingRequestId(), 0, Map.of(
                "test_case", result.getTestCase().getName(),
                "step_number", step.getStepNumber(),
                "environment", result.getEnvironment()
            ));
        }
    }
}
```

### 3. Performance Optimization

Implement caching and connection pooling:

```java
// Connection pooling
private static final HttpClient httpClient = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(5))
    .build();

// Response caching
private final Cache<String, HealingResult> healingCache =
    CacheBuilder.newBuilder()
        .maximumSize(1000)
        .expireAfterWrite(10, TimeUnit.MINUTES)
        .build();
```

## Configuration Options

### Healing Thresholds

```yaml
healing:
  enabled: true
  api_url: "http://localhost:8000"
  timeout: 5000
  max_candidates: 3
  min_score_threshold: 0.7
  auto_apply: true
  retry_failed_healing: true
```

### Strategy Configuration

```yaml
healing_strategies:
  - name: "heuristics"
    enabled: true
    priority: 1
  - name: "hierarchy"
    enabled: true
    priority: 2
  - name: "llm"
    enabled: false
    priority: 3
    provider: "openai"
```

## Monitoring & Observability

### Metrics Collection

```java
// In HealingService
@Timed(value = "healing.request.duration")
public HealingResult heal(@Valid HealingRequest request) {
    // Healing logic
    return result;
}

@Counted(value = "healing.request.total")
public HealingResult heal(@Valid HealingRequest request) {
    // Healing logic
    return result;
}
```

### Logging Integration

```java
// Structured logging
private static final Logger logger = LoggerFactory.getLogger(HealingService.class);

public void logHealingAttempt(HealingResult result) {
    logger.info("Healing attempt completed",
        keyValue("request_id", result.getRequestId()),
        keyValue("original_locator", result.getOriginalLocator()),
        keyValue("candidates_found", result.getCandidates().size()),
        keyValue("top_score", result.getTopScore()),
        keyValue("healing_strategy", result.getStrategyUsed()));
}
```

## Testing Integration

### Unit Tests

```java
@Test
public void testHealingIntegration() {
    // Mock WebDriver
    WebDriver mockDriver = mock(WebDriver.class);
    when(mockDriver.getPageSource()).thenReturn("<html>...</html>");

    // Test healing service
    HealingService service = new HealingService(mockDriver);
    HealingResult result = service.heal("#missing-element", "css");

    assertThat(result.getCandidates()).isNotEmpty();
    assertThat(result.getTopCandidate().getScore()).isGreaterThan(0.5);
}
```

### Integration Tests

```java
@SpringBootTest
public class HealingIntegrationTest {

    @Autowired
    private HealingService healingService;

    @Test
    public void testEndToEndHealing() {
        // Setup test page
        driver.get("http://test-app/login");

        // Attempt to find non-existent element (should trigger healing)
        assertThrows(NoSuchElementException.class, () ->
            driver.findElement(By.cssSelector("#non-existent")));

        // Verify healing was attempted and logged
        verify(healingService).heal(anyString(), anyString());
    }
}
```

## Troubleshooting

### Common Issues

#### API Connection Failures

```java
// Implement retry logic
@Retryable(value = {IOException.class}, maxAttempts = 3)
public HealingResult healWithRetry(HealingRequest request) {
    return healingService.heal(request);
}
```

#### Healing Quality Issues

```java
// Adjust context building
private Map<String, Object> buildRichContext(WebDriver driver, By failedLocator) {
    // Extract more context around the failed locator
    // Use JavaScript to get element attributes, position, etc.
    return context;
}
```

#### Performance Concerns

```java
// Async healing for non-blocking operation
@Async
public CompletableFuture<HealingResult> healAsync(HealingRequest request) {
    return CompletableFuture.completedFuture(healingService.heal(request));
}
```

## Best Practices

### 1. Configuration Management

- Use environment-specific configurations
- Implement feature flags for gradual rollout
- Monitor healing effectiveness metrics

### 2. Error Handling

- Implement circuit breakers for API failures
- Provide fallback strategies when healing fails
- Log healing attempts for analysis

### 3. Performance

- Cache healing results when appropriate
- Use connection pooling for API calls
- Implement timeouts to prevent hanging

### 4. Security

- Validate HTML input to prevent XSS
- Use HTTPS for API communications
- Implement authentication for production deployments

### 5. Monitoring

- Track healing success rates
- Monitor API latency and error rates
- Alert on healing quality degradation

## Migration Guide

### From Manual Healing

1. **Phase 1**: Deploy healing service alongside existing tests
2. **Phase 2**: Enable healing for non-critical tests
3. **Phase 3**: Gradually enable for all test suites
4. **Phase 4**: Remove manual healing code

### From Other Healing Solutions

1. **Assessment**: Evaluate current healing effectiveness
2. **Integration**: Implement alongside existing solution
3. **Comparison**: A/B test healing quality and performance
4. **Migration**: Gradually phase out old solution

## Support

For APEX integration support:

- **Documentation**: Refer to APEX integration guides
- **Issues**: File issues in the self-heal-engine repository
- **Discussions**: Use GitHub Discussions for integration questions
- **Professional Services**: Contact the development team for custom integrations

---

*This integration guide is specific to APEX. For other test automation platforms, similar integration patterns can be applied.*
