package com.example.ecommerce.entity;

import lombok.Data;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class Orders {
    private Integer id;
    private Integer userId;
    private Integer productId;
    private Integer quantity;
    private BigDecimal totalPrice;
    private LocalDateTime orderTime;
}
