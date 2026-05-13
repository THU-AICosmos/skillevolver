#!/bin/bash
# Solution for Spring Boot 2 to 3 Migration Task (Product Catalog Variant)
# Migrates the legacy catalog application to modern Spring Boot 3.2

set -e

echo "=== Beginning Product Catalog Spring Boot Migration ==="

# Navigate to project root
cd /workspace

# Step 1: Replace pom.xml with Spring Boot 3.2 + Java 21 + updated deps
echo "[1/7] Rewriting pom.xml for Spring Boot 3.2..."
cat > pom.xml << 'POM_END'
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>catalogservice</artifactId>
    <version>2.0.0</version>
    <name>Catalog Service</name>
    <description>Modernized Product Catalog Microservice</description>

    <properties>
        <java.version>21</java.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>

        <!-- Database -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- JWT Support (modular artifacts for Java 21) -->
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-api</artifactId>
            <version>0.12.3</version>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-impl</artifactId>
            <version>0.12.3</version>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-jackson</artifactId>
            <version>0.12.3</version>
            <scope>runtime</scope>
        </dependency>

        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>

        <dependency>
            <groupId>org.springframework.security</groupId>
            <artifactId>spring-security-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
POM_END

# Step 2: Migrate Product.java to jakarta namespace
echo "[2/7] Migrating Product.java to jakarta namespace..."
cat > src/main/java/com/example/catalogservice/model/Product.java << 'JAVA_END'
package com.example.catalogservice.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "products")
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank(message = "Product name is required")
    @Size(min = 2, max = 100, message = "Product name must be between 2 and 100 characters")
    @Column(nullable = false)
    private String name;

    @Size(max = 500, message = "Description cannot exceed 500 characters")
    @Column(length = 500)
    private String description;

    @NotNull(message = "Price is required")
    @DecimalMin(value = "0.01", message = "Price must be at least 0.01")
    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal price;

    @NotBlank(message = "SKU is required")
    @Column(unique = true, nullable = false)
    private String sku;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Category category = Category.ELECTRONICS;

    @Column(nullable = false)
    private int stockQuantity = 0;

    @Column(nullable = false)
    private boolean available = true;

    @Column(name = "brand")
    private String brand;

    @Column(name = "weight_kg")
    private Double weightKg;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    // Constructors
    public Product() {}

    public Product(String name, String sku, BigDecimal price) {
        this.name = name;
        this.sku = sku;
        this.price = price;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public BigDecimal getPrice() { return price; }
    public void setPrice(BigDecimal price) { this.price = price; }

    public String getSku() { return sku; }
    public void setSku(String sku) { this.sku = sku; }

    public Category getCategory() { return category; }
    public void setCategory(Category category) { this.category = category; }

    public int getStockQuantity() { return stockQuantity; }
    public void setStockQuantity(int stockQuantity) { this.stockQuantity = stockQuantity; }

    public boolean isAvailable() { return available; }
    public void setAvailable(boolean available) { this.available = available; }

    public String getBrand() { return brand; }
    public void setBrand(String brand) { this.brand = brand; }

    public Double getWeightKg() { return weightKg; }
    public void setWeightKg(Double weightKg) { this.weightKg = weightKg; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}
JAVA_END

# Step 3: Migrate CreateProductRequest.java to jakarta namespace
echo "[3/7] Migrating CreateProductRequest.java to jakarta namespace..."
cat > src/main/java/com/example/catalogservice/dto/CreateProductRequest.java << 'JAVA_END'
package com.example.catalogservice.dto;

import com.example.catalogservice.model.Category;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;

public class CreateProductRequest {

    @NotBlank(message = "Product name is required")
    @Size(min = 2, max = 100, message = "Product name must be between 2 and 100 characters")
    private String name;

    @Size(max = 500, message = "Description cannot exceed 500 characters")
    private String description;

    @NotNull(message = "Price is required")
    @DecimalMin(value = "0.01", message = "Price must be at least 0.01")
    private BigDecimal price;

    @NotBlank(message = "SKU is required")
    private String sku;

    private Category category;
    private int stockQuantity;
    private String brand;
    private Double weightKg;

    // Constructors
    public CreateProductRequest() {}

    public CreateProductRequest(String name, String sku, BigDecimal price) {
        this.name = name;
        this.sku = sku;
        this.price = price;
    }

    // Getters and Setters
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public BigDecimal getPrice() { return price; }
    public void setPrice(BigDecimal price) { this.price = price; }

    public String getSku() { return sku; }
    public void setSku(String sku) { this.sku = sku; }

    public Category getCategory() { return category; }
    public void setCategory(Category category) { this.category = category; }

    public int getStockQuantity() { return stockQuantity; }
    public void setStockQuantity(int stockQuantity) { this.stockQuantity = stockQuantity; }

    public String getBrand() { return brand; }
    public void setBrand(String brand) { this.brand = brand; }

    public Double getWeightKg() { return weightKg; }
    public void setWeightKg(Double weightKg) { this.weightKg = weightKg; }
}
JAVA_END

# Step 4: Migrate ProductService.java to jakarta namespace
echo "[4/7] Migrating ProductService.java to jakarta namespace..."
cat > src/main/java/com/example/catalogservice/service/ProductService.java << 'JAVA_END'
package com.example.catalogservice.service;

import com.example.catalogservice.dto.CreateProductRequest;
import com.example.catalogservice.dto.ProductDTO;
import com.example.catalogservice.model.Category;
import com.example.catalogservice.model.Product;
import com.example.catalogservice.repository.ProductRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.persistence.EntityNotFoundException;
import java.math.BigDecimal;
import java.util.List;
import java.util.stream.Collectors;

@Service
@Transactional
public class ProductService {

    private final ProductRepository productRepository;

    @Autowired
    public ProductService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    public List<ProductDTO> getAllProducts() {
        return productRepository.findAll()
                .stream()
                .map(ProductDTO::new)
                .collect(Collectors.toList());
    }

    public ProductDTO getProductById(Long id) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Product not found with id: " + id));
        return new ProductDTO(product);
    }

    public ProductDTO getProductBySku(String sku) {
        Product product = productRepository.findBySku(sku)
                .orElseThrow(() -> new EntityNotFoundException("Product not found with SKU: " + sku));
        return new ProductDTO(product);
    }

    public ProductDTO createProduct(CreateProductRequest request) {
        if (productRepository.existsBySku(request.getSku())) {
            throw new IllegalArgumentException("SKU already exists");
        }

        Product product = new Product();
        product.setName(request.getName());
        product.setDescription(request.getDescription());
        product.setPrice(request.getPrice());
        product.setSku(request.getSku());
        product.setCategory(request.getCategory() != null ? request.getCategory() : Category.ELECTRONICS);
        product.setStockQuantity(request.getStockQuantity());
        product.setBrand(request.getBrand());
        product.setWeightKg(request.getWeightKg());

        Product savedProduct = productRepository.save(product);
        return new ProductDTO(savedProduct);
    }

    public ProductDTO updateProduct(Long id, CreateProductRequest request) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Product not found with id: " + id));

        if (!product.getSku().equals(request.getSku()) &&
                productRepository.existsBySku(request.getSku())) {
            throw new IllegalArgumentException("SKU already exists");
        }

        product.setName(request.getName());
        product.setDescription(request.getDescription());
        product.setPrice(request.getPrice());
        product.setSku(request.getSku());
        if (request.getCategory() != null) {
            product.setCategory(request.getCategory());
        }
        product.setStockQuantity(request.getStockQuantity());
        product.setBrand(request.getBrand());
        product.setWeightKg(request.getWeightKg());

        Product savedProduct = productRepository.save(product);
        return new ProductDTO(savedProduct);
    }

    public void deleteProduct(Long id) {
        if (!productRepository.existsById(id)) {
            throw new EntityNotFoundException("Product not found with id: " + id);
        }
        productRepository.deleteById(id);
    }

    public ProductDTO markUnavailable(Long id) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new EntityNotFoundException("Product not found with id: " + id));
        product.setAvailable(false);
        Product savedProduct = productRepository.save(product);
        return new ProductDTO(savedProduct);
    }

    public List<ProductDTO> getAvailableProducts() {
        return productRepository.findByAvailableTrue()
                .stream()
                .map(ProductDTO::new)
                .collect(Collectors.toList());
    }

    public List<ProductDTO> getProductsByCategory(Category category) {
        return productRepository.findByCategory(category)
                .stream()
                .map(ProductDTO::new)
                .collect(Collectors.toList());
    }

    public List<ProductDTO> getProductsByPriceRange(BigDecimal minPrice, BigDecimal maxPrice) {
        return productRepository.findByPriceRange(minPrice, maxPrice)
                .stream()
                .map(ProductDTO::new)
                .collect(Collectors.toList());
    }

    public List<ProductDTO> searchProducts(String searchTerm) {
        return productRepository.searchProducts(searchTerm)
                .stream()
                .map(ProductDTO::new)
                .collect(Collectors.toList());
    }
}
JAVA_END

# Step 5: Migrate ExternalPricingService.java - RestTemplate to RestClient
echo "[5/7] Migrating ExternalPricingService.java to RestClient..."
cat > src/main/java/com/example/catalogservice/service/ExternalPricingService.java << 'JAVA_END'
package com.example.catalogservice.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.Map;

/**
 * Service for making external pricing and inventory API calls using RestClient (Spring 6.1+).
 * Migrated from legacy RestTemplate.
 */
@Service
public class ExternalPricingService {

    private final RestClient restClient;

    @Value("${external.pricing.base-url:https://pricing.example.com}")
    private String baseUrl;

    public ExternalPricingService() {
        this.restClient = RestClient.create();
    }

    /**
     * Check current market price for a product SKU
     */
    public BigDecimal getMarketPrice(String sku) {
        try {
            Map<String, Object> response = restClient.get()
                .uri(baseUrl + "/prices/sku?sku={sku}", sku)
                .retrieve()
                .body(new ParameterizedTypeReference<Map<String, Object>>() {});

            if (response != null) {
                Object price = response.get("marketPrice");
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
            Map<String, Object> payload = Map.of(
                "productId", productId,
                "quantity", newQuantity,
                "eventType", "STOCK_UPDATE"
            );

            restClient.post()
                .uri(baseUrl + "/warehouse/stock-updates")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_JSON)
                .body(payload)
                .retrieve()
                .toBodilessEntity();
        } catch (Exception e) {
            System.err.println("Failed to notify warehouse: " + e.getMessage());
        }
    }

    /**
     * Fetch supplier information for a product
     */
    public Map<String, Object> getSupplierInfo(String productId) {
        try {
            Map<String, Object> response = restClient.get()
                .uri(baseUrl + "/suppliers/{id}/details", productId)
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(new ParameterizedTypeReference<Map<String, Object>>() {});

            return response != null ? response : Collections.emptyMap();
        } catch (Exception e) {
            return Collections.emptyMap();
        }
    }

    /**
     * Remove product listing from external marketplace
     */
    public boolean removeFromMarketplace(String productId) {
        try {
            restClient.delete()
                .uri(baseUrl + "/marketplace/{id}/listing", productId)
                .retrieve()
                .toBodilessEntity();
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
JAVA_END

# Step 6: Migrate ProductController.java to jakarta namespace
echo "[6/7] Migrating ProductController.java to jakarta namespace..."
cat > src/main/java/com/example/catalogservice/controller/ProductController.java << 'JAVA_END'
package com.example.catalogservice.controller;

import com.example.catalogservice.dto.CreateProductRequest;
import com.example.catalogservice.dto.ProductDTO;
import com.example.catalogservice.model.Category;
import com.example.catalogservice.service.ProductService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import jakarta.validation.Valid;
import java.math.BigDecimal;
import java.util.List;

@RestController
@RequestMapping("/api/products")
public class ProductController {

    private final ProductService productService;

    @Autowired
    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping
    public ResponseEntity<List<ProductDTO>> getAllProducts() {
        List<ProductDTO> products = productService.getAllProducts();
        return ResponseEntity.ok(products);
    }

    @GetMapping("/{id}")
    public ResponseEntity<ProductDTO> getProductById(@PathVariable Long id) {
        ProductDTO product = productService.getProductById(id);
        return ResponseEntity.ok(product);
    }

    @GetMapping("/sku/{sku}")
    @PreAuthorize("hasRole('MANAGER') or hasRole('ADMIN')")
    public ResponseEntity<ProductDTO> getProductBySku(@PathVariable String sku) {
        ProductDTO product = productService.getProductBySku(sku);
        return ResponseEntity.ok(product);
    }

    @PostMapping
    @PreAuthorize("hasRole('MANAGER') or hasRole('ADMIN')")
    public ResponseEntity<ProductDTO> createProduct(@Valid @RequestBody CreateProductRequest request) {
        ProductDTO createdProduct = productService.createProduct(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(createdProduct);
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('MANAGER') or hasRole('ADMIN')")
    public ResponseEntity<ProductDTO> updateProduct(
            @PathVariable Long id,
            @Valid @RequestBody CreateProductRequest request) {
        ProductDTO updatedProduct = productService.updateProduct(id, request);
        return ResponseEntity.ok(updatedProduct);
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<Void> deleteProduct(@PathVariable Long id) {
        productService.deleteProduct(id);
        return ResponseEntity.noContent().build();
    }

    @PatchMapping("/{id}/unavailable")
    @PreAuthorize("hasRole('MANAGER') or hasRole('ADMIN')")
    public ResponseEntity<ProductDTO> markUnavailable(@PathVariable Long id) {
        ProductDTO product = productService.markUnavailable(id);
        return ResponseEntity.ok(product);
    }

    @GetMapping("/available")
    public ResponseEntity<List<ProductDTO>> getAvailableProducts() {
        List<ProductDTO> products = productService.getAvailableProducts();
        return ResponseEntity.ok(products);
    }

    @GetMapping("/category/{category}")
    public ResponseEntity<List<ProductDTO>> getProductsByCategory(@PathVariable Category category) {
        List<ProductDTO> products = productService.getProductsByCategory(category);
        return ResponseEntity.ok(products);
    }

    @GetMapping("/price-range")
    public ResponseEntity<List<ProductDTO>> getProductsByPriceRange(
            @RequestParam BigDecimal min, @RequestParam BigDecimal max) {
        List<ProductDTO> products = productService.getProductsByPriceRange(min, max);
        return ResponseEntity.ok(products);
    }

    @GetMapping("/search")
    public ResponseEntity<List<ProductDTO>> searchProducts(@RequestParam String q) {
        List<ProductDTO> products = productService.searchProducts(q);
        return ResponseEntity.ok(products);
    }
}
JAVA_END

# Step 7: Migrate SecurityConfig.java to Spring Security 6 component-based style
echo "[7/7] Migrating SecurityConfig.java to Spring Security 6..."
cat > src/main/java/com/example/catalogservice/config/SecurityConfig.java << 'JAVA_END'
package com.example.catalogservice.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

import jakarta.servlet.http.HttpServletResponse;

/**
 * Security configuration using Spring Security 6 component-based approach.
 * Migrated from deprecated WebSecurityConfigurerAdapter.
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity(prePostEnabled = true)
public class SecurityConfig {

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public AuthenticationManager authenticationManager(
            AuthenticationConfiguration authConfig) throws Exception {
        return authConfig.getAuthenticationManager();
    }

    @Bean
    public SecurityFilterChain catalogSecurityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint((request, response, authException) -> {
                    response.sendError(HttpServletResponse.SC_UNAUTHORIZED,
                        authException.getMessage());
                })
            )
            .authorizeHttpRequests(auth -> auth
                // Public endpoints - anyone can browse products
                .requestMatchers(HttpMethod.GET, "/api/products").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/products/available").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/products/category/**").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/products/search").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/products/price-range").permitAll()
                .requestMatchers(HttpMethod.GET, "/api/products/{id}").permitAll()
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/h2-console/**").permitAll()
                .requestMatchers("/actuator/health").permitAll()
                // All other endpoints require authentication
                .anyRequest().authenticated()
            )
            .headers(headers -> headers
                .frameOptions(frame -> frame.disable()) // For H2 console
            );

        return http.build();
    }
}
JAVA_END

# Step 8: Migrate GlobalExceptionHandler.java to jakarta namespace
echo "Migrating GlobalExceptionHandler.java to jakarta namespace..."
cat > src/main/java/com/example/catalogservice/exception/GlobalExceptionHandler.java << 'JAVA_END'
package com.example.catalogservice.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import jakarta.persistence.EntityNotFoundException;
import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(EntityNotFoundException.class)
    public ResponseEntity<ApiError> handleEntityNotFound(
            EntityNotFoundException ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.NOT_FOUND.value(),
                "Resource Not Found",
                ex.getMessage(),
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiError> handleIllegalArgument(
            IllegalArgumentException ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.BAD_REQUEST.value(),
                "Invalid Request",
                ex.getMessage(),
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(apiError);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationApiError> handleValidationErrors(
            MethodArgumentNotValidException ex,
            HttpServletRequest request) {
        Map<String, String> fieldErrors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach((error) -> {
            String fieldName = ((FieldError) error).getField();
            String errorMessage = error.getDefaultMessage();
            fieldErrors.put(fieldName, errorMessage);
        });

        ValidationApiError apiError = new ValidationApiError(
                HttpStatus.BAD_REQUEST.value(),
                "Validation Error",
                fieldErrors,
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(apiError);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ApiError> handleAccessDenied(
            AccessDeniedException ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.FORBIDDEN.value(),
                "Access Denied",
                "Insufficient permissions to access this resource",
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(apiError);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiError> handleGenericException(
            Exception ex,
            HttpServletRequest request) {
        ApiError apiError = new ApiError(
                HttpStatus.INTERNAL_SERVER_ERROR.value(),
                "Server Error",
                "An unexpected error occurred",
                request.getRequestURI()
        );
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(apiError);
    }

    // Error response classes
    public static class ApiError {
        private final LocalDateTime timestamp;
        private final int statusCode;
        private final String errorType;
        private final String detail;
        private final String requestPath;

        public ApiError(int statusCode, String errorType, String detail, String requestPath) {
            this.timestamp = LocalDateTime.now();
            this.statusCode = statusCode;
            this.errorType = errorType;
            this.detail = detail;
            this.requestPath = requestPath;
        }

        public LocalDateTime getTimestamp() { return timestamp; }
        public int getStatusCode() { return statusCode; }
        public String getErrorType() { return errorType; }
        public String getDetail() { return detail; }
        public String getRequestPath() { return requestPath; }
    }

    public static class ValidationApiError {
        private final LocalDateTime timestamp;
        private final int statusCode;
        private final String errorType;
        private final Map<String, String> fieldErrors;
        private final String requestPath;

        public ValidationApiError(int statusCode, String errorType, Map<String, String> fieldErrors, String requestPath) {
            this.timestamp = LocalDateTime.now();
            this.statusCode = statusCode;
            this.errorType = errorType;
            this.fieldErrors = fieldErrors;
            this.requestPath = requestPath;
        }

        public LocalDateTime getTimestamp() { return timestamp; }
        public int getStatusCode() { return statusCode; }
        public String getErrorType() { return errorType; }
        public Map<String, String> getFieldErrors() { return fieldErrors; }
        public String getRequestPath() { return requestPath; }
    }
}
JAVA_END

echo "=== Migration files written. Building project... ==="

# Source SDKMAN and switch to Java 21
source /root/.sdkman/bin/sdkman-init.sh
sdk use java 21.0.2-tem

# Compile
mvn clean compile -q

echo "=== Compilation successful! Running tests... ==="

# Run tests
mvn test -q

echo "=== All tests passed! Product Catalog migration completed successfully. ==="
