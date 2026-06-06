package com.example.ecommerce.entity;

import lombok.Data;
import java.math.BigDecimal;

/**
 * 订单详情VO - 包含关联的用户名和商品名
 */
@Data
public class OrderDetailVO {
    private Integer orderId;
    private String userName;
    private String productName;
    private Integer quantity;
    private BigDecimal totalPrice;
    private String orderTime;
}
