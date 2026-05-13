package com.example.catalogservice.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Map;

/**
 * Service for making external pricing and inventory API calls using RestTemplate.
 * This is a legacy pattern that should be migrated to RestClient in Spring Boot 3.
 */
@Service
public class ExternalPricingService {

    private final RestTemplate restTemplate;

    @Value("${external.pricing.base-url:https://pricing.example.com}")
    private String baseUrl;

    public ExternalPricingService() {
        this.restTemplate = new RestTemplate();
    }

    /**
     * Check current market price for a product SKU
     */
    public BigDecimal getMarketPrice(String sku) {
        try {
            String url = baseUrl + "/prices/sku?sku=" + sku;
            ResponseEntity<Map> response = restTemplate.getForEntity(url, Map.class);
            if (response.getBody() != null) {
                Object price = response.getBody().get("marketPrice");
                return price != null ? new BigDecimal(price.toString()) : BigDecimal.ZERO;
            }
            return BigDecimal.ZERO;
        } catch (Exception e) {
            return BigDecimal.ZERO;
        }
    }

    /**
     * Notify warehouse about stock level changes
     */
    public void notifyStockChange(String productId, int newQuantity) {
        try {
            String url = baseUrl + "/warehouse/stock-updates";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.setAccept(Collections.singletonList(MediaType.APPLICATION_JSON));

            Map<String, Object> payload = Map.of(
                "productId", productId,
                "quantity", newQuantity,
                "eventType", "STOCK_UPDATE"
            );

            HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);
            restTemplate.postForEntity(url, request, Void.class);
        } catch (Exception e) {
            System.err.println("Failed to notify warehouse: " + e.getMessage());
        }
    }

    /**
     * Fetch supplier information for a product
     */
    public Map<String, Object> getSupplierInfo(String productId) {
        try {
            String url = baseUrl + "/suppliers/" + productId + "/details";

            HttpHeaders headers = new HttpHeaders();
            headers.setAccept(Collections.singletonList(MediaType.APPLICATION_JSON));

            HttpEntity<?> request = new HttpEntity<>(headers);

            ResponseEntity<Map> response = restTemplate.exchange(
                url,
                HttpMethod.GET,
                request,
                Map.class
            );

            return response.getBody() != null ? response.getBody() : Collections.emptyMap();
        } catch (Exception e) {
            return Collections.emptyMap();
        }
    }

    /**
     * Remove product listing from external marketplace
     */
    public boolean removeFromMarketplace(String productId) {
        try {
            String url = baseUrl + "/marketplace/" + productId + "/listing";
            restTemplate.delete(url);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
