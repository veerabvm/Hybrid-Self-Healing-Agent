import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.openqa.selenium.By;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.support.ui.WebDriverWait;
import org.openqa.selenium.support.ui.ExpectedConditions;

/**
 * Java helper class for integrating with the Self-Healing Engine API.
 *
 * This class demonstrates how to call the healing API and perform
 * verification actions using Selenium WebDriver.
 */
public class HealingHelper {

    private static final String HEALING_API_URL = "http://localhost:8000";
    private static final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    private static final ObjectMapper objectMapper = new ObjectMapper();

    private final WebDriver driver;
    private final String apiBaseUrl;

    public HealingHelper(WebDriver driver) {
        this(driver, HEALING_API_URL);
    }

    public HealingHelper(WebDriver driver, String apiBaseUrl) {
        this.driver = driver;
        this.apiBaseUrl = apiBaseUrl;
    }

    /**
     * Attempt to heal a failed locator and return the best candidate.
     *
     * @param originalLocator The locator that failed
     * @param locatorType Type of locator (css, xpath, id, name)
     * @param context Additional context (anchors, sibling text, etc.)
     * @return The healed locator, or null if healing failed
     */
    public String healLocator(String originalLocator, String locatorType, Map<String, Object> context) {
        try {
            // Get current page HTML
            String pageHtml = driver.getPageSource();

            // Prepare healing request
            Map<String, Object> requestBody = Map.of(
                "html", pageHtml,
                "original_locator", originalLocator,
                "locator_type", locatorType,
                "context", context != null ? context : Map.of(),
                "max_candidates", 5,
                "use_llm", false
            );

            // Call healing API
            HealingResponse response = callHealingApi(requestBody);

            if (response == null || response.getCandidates().isEmpty()) {
                System.out.println("No healing candidates found");
                return null;
            }

            // Get the best candidate
            Candidate bestCandidate = response.getCandidates().get(0);
            String healedLocator = bestCandidate.getLocator();

            // Perform verification
            boolean verified = performVerification(bestCandidate, response.getVerifyAction());
            if (!verified) {
                System.out.println("Verification failed for healed locator: " + healedLocator);
                return null;
            }

            // Confirm the successful healing
            confirmHealing(response.getRequestId(), 0);

            System.out.println("Successfully healed locator: " + originalLocator + " -> " + healedLocator);
            return healedLocator;

        } catch (Exception e) {
            System.err.println("Healing failed: " + e.getMessage());
            return null;
        }
    }

    /**
     * Call the healing API.
     */
    private HealingResponse callHealingApi(Map<String, Object> requestBody) throws IOException, InterruptedException {
        String requestJson = objectMapper.writeValueAsString(requestBody);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(apiBaseUrl + "/heal"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestJson))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new RuntimeException("API call failed with status: " + response.statusCode());
        }

        return objectMapper.readValue(response.body(), HealingResponse.class);
    }

    /**
     * Perform verification action on the healed locator.
     */
    private boolean performVerification(Candidate candidate, Map<String, Object> verifyAction) {
        try {
            String actionType = (String) verifyAction.get("type");

            switch (actionType) {
                case "exists":
                    return verifyElementExists(candidate.getLocator(), candidate.getType());

                case "click_and_check":
                    return verifyClickAndCheck(candidate.getLocator(), candidate.getType(), verifyAction);

                default:
                    System.out.println("Unknown verification action: " + actionType);
                    return false;
            }
        } catch (Exception e) {
            System.err.println("Verification failed: " + e.getMessage());
            return false;
        }
    }

    /**
     * Verify that an element exists.
     */
    private boolean verifyElementExists(String locator, String locatorType) {
        try {
            WebDriverWait wait = new WebDriverWait(driver, Duration.ofSeconds(5));
            By seleniumLocator = convertToSeleniumLocator(locator, locatorType);

            WebElement element = wait.until(ExpectedConditions.presenceOfElementLocated(seleniumLocator));
            return element != null;

        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Verify clicking an element doesn't cause errors.
     */
    private boolean verifyClickAndCheck(String locator, String locatorType, Map<String, Object> verifyAction) {
        try {
            By seleniumLocator = convertToSeleniumLocator(locator, locatorType);
            WebElement element = driver.findElement(seleniumLocator);

            // Store current URL
            String originalUrl = driver.getCurrentUrl();

            // Click the element
            element.click();

            // Wait a bit for any navigation or errors
            Thread.sleep(2000);

            // Check if we're still on the same page (unless URL change was expected)
            boolean urlChangeExpected = (Boolean) verifyAction.getOrDefault("expected_url_change", false);
            if (!urlChangeExpected && !driver.getCurrentUrl().equals(originalUrl)) {
                return false; // Unexpected navigation
            }

            // Check for error elements
            @SuppressWarnings("unchecked")
            List<String> errorSelectors = (List<String>) verifyAction.getOrDefault("error_selectors", List.of());
            for (String errorSelector : errorSelectors) {
                try {
                    List<WebElement> errorElements = driver.findElements(By.cssSelector(errorSelector));
                    if (!errorElements.isEmpty()) {
                        return false; // Error elements found
                    }
                } catch (Exception e) {
                    // Ignore selector errors
                }
            }

            return true;

        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Confirm a successful healing to the API.
     */
    private void confirmHealing(String requestId, int acceptedIndex) {
        try {
            Map<String, Object> confirmBody = Map.of(
                "request_id", requestId,
                "accepted_index", acceptedIndex
            );

            String confirmJson = objectMapper.writeValueAsString(confirmBody);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(apiBaseUrl + "/confirm"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(confirmJson))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() == 200) {
                System.out.println("Healing confirmed successfully");
            } else {
                System.err.println("Failed to confirm healing: " + response.statusCode());
            }

        } catch (Exception e) {
            System.err.println("Error confirming healing: " + e.getMessage());
        }
    }

    /**
     * Convert API locator format to Selenium By object.
     */
    private By convertToSeleniumLocator(String locator, String locatorType) {
        switch (locatorType.toLowerCase()) {
            case "css":
                return By.cssSelector(locator);
            case "xpath":
                return By.xpath(locator);
            case "id":
                return By.id(locator);
            case "name":
                return By.name(locator);
            default:
                throw new IllegalArgumentException("Unsupported locator type: " + locatorType);
        }
    }

    // POJO classes for JSON deserialization

    public static class HealingResponse {
        private String requestId;
        private List<Candidate> candidates;
        private int autoApplyIndex;
        private Map<String, Object> verifyAction;

        // Getters and setters
        public String getRequestId() { return requestId; }
        public void setRequestId(String requestId) { this.requestId = requestId; }

        public List<Candidate> getCandidates() { return candidates; }
        public void setCandidates(List<Candidate> candidates) { this.candidates = candidates; }

        public int getAutoApplyIndex() { return autoApplyIndex; }
        public void setAutoApplyIndex(int autoApplyIndex) { this.autoApplyIndex = autoApplyIndex; }

        public Map<String, Object> getVerifyAction() { return verifyAction; }
        public void setVerifyAction(Map<String, Object> verifyAction) { this.verifyAction = verifyAction; }
    }

    public static class Candidate {
        private String locator;
        private String type;
        private double score;
        private String reason;
        private Map<String, Object> features;

        // Getters and setters
        public String getLocator() { return locator; }
        public void setLocator(String locator) { this.locator = locator; }

        public String getType() { return type; }
        public void setType(String type) { this.type = type; }

        public double getScore() { return score; }
        public void setScore(double score) { this.score = score; }

        public String getReason() { return reason; }
        public void setReason(String reason) { this.reason = reason; }

        public Map<String, Object> getFeatures() { return features; }
        public void setFeatures(Map<String, Object> features) { this.features = features; }
    }

    /**
     * Example usage.
     */
    public static void main(String[] args) {
        // Setup WebDriver (example with Chrome)
        System.setProperty("webdriver.chrome.driver", "/path/to/chromedriver");
        WebDriver driver = new ChromeDriver();

        try {
            // Navigate to a page
            driver.get("https://example.com");

            // Create healing helper
            HealingHelper healer = new HealingHelper(driver);

            // Example healing request
            Map<String, Object> context = Map.of(
                "anchors", List.of("Login", "Username"),
                "prev_sibling_text", "Welcome back"
            );

            // Attempt to heal a locator
            String healedLocator = healer.healLocator("#old-login-btn", "css", context);

            if (healedLocator != null) {
                System.out.println("Healed locator: " + healedLocator);
                // Use the healed locator in your tests
                WebElement element = driver.findElement(By.cssSelector(healedLocator));
                element.click();
            } else {
                System.out.println("Could not heal the locator");
            }

        } finally {
            driver.quit();
        }
    }
}
