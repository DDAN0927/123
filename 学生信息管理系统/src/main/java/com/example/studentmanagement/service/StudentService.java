package com.example.studentmanagement.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.example.studentmanagement.entity.Student;

public interface StudentService extends IService<Student> {

    /**
     * 新增学生
     */
    void addStudent(Student student);

    /**
     * 根据ID删除学生
     */
    void deleteStudent(Long id);

    /**
     * 根据ID更新学生信息
     */
    void updateStudent(Student student);

    /**
     * 根据ID查询学生详情
     */
    Student getStudentById(Long id);

    /**
     * 分页查询学生列表（支持按姓名模糊搜索）
     */
    IPage<Student> listStudents(Integer page, Integer pageSize, String name);
}
