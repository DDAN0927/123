package com.example.ecommerce.service;

import com.example.ecommerce.entity.OrderDetailVO;

public interface OrdersService {

    /**
     * 创建订单
     */
    OrderDetailVO createOrder(Integer userId, Integer productId, Integer quantity);

    /**
     * 查询订单详情
     */
    OrderDetailVO getOrderDetail(Integer orderId);
}
