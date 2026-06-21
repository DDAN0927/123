package com.example.ecommerce.mapper;

import com.example.ecommerce.entity.Product;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface ProductMapper {

    @Select("SELECT id, product_name, price, stock FROM product WHERE id = #{id}")
    Product selectById(@Param("id") Integer id);

    @Select("SELECT id, product_name, price, stock FROM product")
    List<Product> selectAll();

    int decreaseStock(@Param("id") Integer id, @Param("quantity") Integer quantity);
}
