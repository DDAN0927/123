package com.example.studentmanagement.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.studentmanagement.entity.Student;
import com.example.studentmanagement.mapper.StudentMapper;
import com.example.studentmanagement.service.StudentService;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

@Service
public class StudentServiceImpl extends ServiceImpl<StudentMapper, Student> implements StudentService {

    @Override
    public void addStudent(Student student) {
        save(student);
    }

    @Override
    public void deleteStudent(Long id) {
        removeById(id);
    }

    @Override
    public void updateStudent(Student student) {
        updateById(student);
    }

    @Override
    public Student getStudentById(Long id) {
        return getById(id);
    }

    @Override
    public IPage<Student> listStudents(Integer page, Integer pageSize, String name) {
        Page<Student> pageParam = new Page<>(page, pageSize);
        LambdaQueryWrapper<Student> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(name)) {
            wrapper.like(Student::getName, name);
        }
        wrapper.orderByDesc(Student::getCreateTime);
        return page(pageParam, wrapper);
    }
}
