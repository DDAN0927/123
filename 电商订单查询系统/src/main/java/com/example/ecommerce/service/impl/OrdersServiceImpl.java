package com.example.ecommerce.service.impl;

import com.example.ecommerce.entity.OrderDetailVO;
import com.example.ecommerce.entity.Orders;
import com.example.ecommerce.entity.Product;
import com.example.ecommerce.exception.BusinessException;
import com.example.ecommerce.mapper.OrdersMapper;
import com.example.ecommerce.mapper.ProductMapper;
import com.example.ecommerce.service.OrdersService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Service
public class OrdersServiceImpl implements OrdersService {

    private final ProductMapper productMapper;
    private final OrdersMapper ordersMapper;

    public OrdersServiceImpl(ProductMapper productMapper, OrdersMapper ordersMapper) {
        this.productMapper = productMapper;
        this.ordersMapper = ordersMapper;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public OrderDetailVO createOrder(Integer userId, Integer productId, Integer quantity) {
        // 1. 查询商品信息
        Product product = productMapper.selectById(productId);
        if (product == null) {
            throw new BusinessException("商品不存在");
        }

        // 2. 检查库存是否充足
        if (product.getStock() < quantity) {
            throw new BusinessException("库存不足，当前库存：" + product.getStock());
        }

        // 3. 计算总价
        BigDecimal totalPrice = product.getPrice().multiply(BigDecimal.valueOf(quantity));

        // 4. 扣减库存（利用 SQL 条件 WHERE stock >= quantity 保证原子性）
        int rows = productMapper.decreaseStock(productId, quantity);
        if (rows == 0) {
            throw new BusinessException("库存不足，下单失败");
        }

        // 5. 生成订单记录
        Orders order = new Orders();
        order.setUserId(userId);
        order.setProductId(productId);
        order.setQuantity(quantity);
        order.setTotalPrice(totalPrice);
        order.setOrderTime(LocalDateTime.now());
        ordersMapper.insert(order);

        // 6. 返回订单详情
        return ordersMapper.selectDetailById(order.getId());
    }

    @Override
    public OrderDetailVO getOrderDetail(Integer orderId) {
        OrderDetailVO detail = ordersMapper.selectDetailById(orderId);
        if (detail == null) {
            throw new BusinessException("订单不存在");
        }
        return detail;
    }
}
