package com.example.catalogservice;

import com.example.catalogservice.dto.CreateProductRequest;
import com.example.catalogservice.dto.ProductDTO;
import com.example.catalogservice.model.Category;
import com.example.catalogservice.service.ProductService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@ActiveProfiles("test")
class CatalogServiceApplicationTests {

    @Autowired
    private ProductService productService;

    @Test
    void contextLoads() {
        assertNotNull(productService);
    }

    @Test
    void testCreateProduct() {
        CreateProductRequest request = new CreateProductRequest();
        request.setName("Wireless Headphones");
        request.setSku("WH-1001");
        request.setPrice(new BigDecimal("79.99"));
        request.setDescription("Bluetooth noise-cancelling headphones");
        request.setCategory(Category.ELECTRONICS);
        request.setStockQuantity(150);
        request.setBrand("AudioTech");

        ProductDTO product = productService.createProduct(request);

        assertNotNull(product);
        assertNotNull(product.getId());
        assertEquals("Wireless Headphones", product.getName());
        assertEquals("WH-1001", product.getSku());
        assertEquals(Category.ELECTRONICS, product.getCategory());
        assertTrue(product.isAvailable());
    }

    @Test
    void testGetProductById() {
        CreateProductRequest request = new CreateProductRequest();
        request.setName("Running Shoes");
        request.setSku("RS-2002");
        request.setPrice(new BigDecimal("129.50"));
        request.setCategory(Category.SPORTS);

        ProductDTO createdProduct = productService.createProduct(request);

        ProductDTO foundProduct = productService.getProductById(createdProduct.getId());

        assertNotNull(foundProduct);
        assertEquals(createdProduct.getId(), foundProduct.getId());
        assertEquals("Running Shoes", foundProduct.getName());
    }

    @Test
    void testUpdateProduct() {
        CreateProductRequest createRequest = new CreateProductRequest();
        createRequest.setName("Cotton T-Shirt");
        createRequest.setSku("CT-3003");
        createRequest.setPrice(new BigDecimal("24.99"));
        createRequest.setCategory(Category.CLOTHING);

        ProductDTO createdProduct = productService.createProduct(createRequest);

        CreateProductRequest updateRequest = new CreateProductRequest();
        updateRequest.setName("Cotton T-Shirt");
        updateRequest.setSku("CT-3003");
        updateRequest.setPrice(new BigDecimal("19.99"));
        updateRequest.setDescription("Premium cotton t-shirt on sale");
        updateRequest.setBrand("ComfortWear");

        ProductDTO updatedProduct = productService.updateProduct(createdProduct.getId(), updateRequest);

        assertEquals(new BigDecimal("19.99"), updatedProduct.getPrice());
        assertEquals("ComfortWear", updatedProduct.getBrand());
    }

    @Test
    void testMarkUnavailable() {
        CreateProductRequest request = new CreateProductRequest();
        request.setName("Garden Hose");
        request.setSku("GH-4004");
        request.setPrice(new BigDecimal("34.99"));
        request.setCategory(Category.HOME_GARDEN);

        ProductDTO createdProduct = productService.createProduct(request);
        assertTrue(createdProduct.isAvailable());

        ProductDTO unavailableProduct = productService.markUnavailable(createdProduct.getId());

        assertFalse(unavailableProduct.isAvailable());
    }

    @Test
    void testDuplicateSku() {
        CreateProductRequest request1 = new CreateProductRequest();
        request1.setName("Mystery Novel");
        request1.setSku("BK-5005");
        request1.setPrice(new BigDecimal("14.99"));
        request1.setCategory(Category.BOOKS);

        productService.createProduct(request1);

        CreateProductRequest request2 = new CreateProductRequest();
        request2.setName("Different Book");
        request2.setSku("BK-5005");
        request2.setPrice(new BigDecimal("19.99"));

        assertThrows(IllegalArgumentException.class, () -> {
            productService.createProduct(request2);
        });
    }

    @Test
    void testSearchProducts() {
        CreateProductRequest request = new CreateProductRequest();
        request.setName("Ultra Laptop Pro");
        request.setSku("ULP-6006");
        request.setPrice(new BigDecimal("999.99"));
        request.setDescription("High-performance laptop for professionals");
        request.setCategory(Category.ELECTRONICS);

        productService.createProduct(request);

        var results = productService.searchProducts("Ultra Laptop");
        assertFalse(results.isEmpty());
        assertEquals("Ultra Laptop Pro", results.get(0).getName());
    }
}
