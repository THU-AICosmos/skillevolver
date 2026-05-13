package com.example.catalogservice.service;

import com.example.catalogservice.dto.CreateProductRequest;
import com.example.catalogservice.dto.ProductDTO;
import com.example.catalogservice.model.Category;
import com.example.catalogservice.model.Product;
import com.example.catalogservice.repository.ProductRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.persistence.EntityNotFoundException;
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
