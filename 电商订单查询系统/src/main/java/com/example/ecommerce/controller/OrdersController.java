package com.example.ecommerce.controller;

import com.example.ecommerce.common.Result;
import com.example.ecommerce.entity.OrderDetailVO;
import com.example.ecommerce.service.OrdersService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/orders")
public class OrdersController {

    private final OrdersService ordersService;

    public OrdersController(OrdersService ordersService) {
        this.ordersService = ordersService;
    }

    /**
     * 创建订单
     * POST /api/orders?userId=1&productId=1&quantity=2
     */
    @PostMapping
    public Result<OrderDetailVO> createOrder(@RequestParam Integer userId,
                                             @RequestParam Integer productId,
                                             @RequestParam Integer quantity) {
        OrderDetailVO detail = ordersService.createOrder(userId, productId, quantity);
        return Result.success(detail);
    }

    /**
     * 查询订单详情
     * GET /api/orders/{id}
     */
    @GetMapping("/{id}")
    public Result<OrderDetailVO> getOrderDetail(@PathVariable Integer id) {
        OrderDetailVO detail = ordersService.getOrderDetail(id);
        return Result.success(detail);
    }
}
