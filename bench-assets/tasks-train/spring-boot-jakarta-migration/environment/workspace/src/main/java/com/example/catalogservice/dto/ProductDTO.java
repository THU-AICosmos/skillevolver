package com.example.catalogservice.dto;

import com.example.catalogservice.model.Category;
import com.example.catalogservice.model.Product;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class ProductDTO {

    private Long id;
    private String name;
    private String description;
    private BigDecimal price;
    private String sku;
    private Category category;
    private int stockQuantity;
    private boolean available;
    private String brand;
    private Double weightKg;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public ProductDTO() {}

    public ProductDTO(Product product) {
        this.id = product.getId();
        this.name = product.getName();
        this.description = product.getDescription();
        this.price = product.getPrice();
        this.sku = product.getSku();
        this.category = product.getCategory();
        this.stockQuantity = product.getStockQuantity();
        this.available = product.isAvailable();
        this.brand = product.getBrand();
        this.weightKg = product.getWeightKg();
        this.createdAt = product.getCreatedAt();
        this.updatedAt = product.getUpdatedAt();
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
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
