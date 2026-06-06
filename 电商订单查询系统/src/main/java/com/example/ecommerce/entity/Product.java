package com.example.ecommerce.entity;

import lombok.Data;
import java.math.BigDecimal;

@Data
public class Product {
    private Integer id;
    private String productName;
    private BigDecimal price;
    private Integer stock;
}
