package com.example.ecommerce.mapper;

import com.example.ecommerce.entity.Product;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface ProductMapper {

    Product selectById(@Param("id") Integer id);

    int decreaseStock(@Param("id") Integer id, @Param("quantity") Integer quantity);
}
