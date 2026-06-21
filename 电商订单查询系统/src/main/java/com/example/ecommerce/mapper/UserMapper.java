package com.example.ecommerce.mapper;

import com.example.ecommerce.entity.User;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface UserMapper {

    @Select("SELECT id, username, phone FROM user")
    List<User> selectAll();

    @Select("SELECT id, username, phone FROM user WHERE id = #{id}")
    User selectById(Integer id);
}
