package com.example.ecommerce.controller;

import com.example.ecommerce.entity.Product;
import com.example.ecommerce.entity.User;
import com.example.ecommerce.mapper.ProductMapper;
import com.example.ecommerce.mapper.UserMapper;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class HomeController {

    private final UserMapper userMapper;
    private final ProductMapper productMapper;

    public HomeController(UserMapper userMapper, ProductMapper productMapper) {
        this.userMapper = userMapper;
        this.productMapper = productMapper;
    }

    @GetMapping("/status")
    public Map<String, Object> status() {
        Map<String, Object> result = new HashMap<>();
        result.put("project", "电商订单查询系统");
        result.put("status", "running");
        result.put("version", "1.0.0");

        Map<String, String> apis = new HashMap<>();
        apis.put("查询订单", "GET /api/orders/{id}");
        apis.put("创建订单", "POST /api/orders?userId=1&productId=1&quantity=2");
        apis.put("用户列表", "GET /api/users");
        apis.put("商品列表", "GET /api/products");
        result.put("apis", apis);

        return result;
    }

    @GetMapping("/users")
    public List<User> listUsers() {
        return userMapper.selectAll();
    }

    @GetMapping("/products")
    public List<Product> listProducts() {
        return productMapper.selectAll();
    }
}
