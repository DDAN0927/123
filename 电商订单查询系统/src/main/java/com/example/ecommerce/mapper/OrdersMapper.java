package com.example.ecommerce.mapper;

import com.example.ecommerce.entity.Orders;
import com.example.ecommerce.entity.OrderDetailVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface OrdersMapper {

    int insert(Orders orders);

    OrderDetailVO selectDetailById(@Param("id") Integer id);
}
