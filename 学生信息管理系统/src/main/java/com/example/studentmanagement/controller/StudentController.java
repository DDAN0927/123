package com.example.studentmanagement.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.example.studentmanagement.common.Result;
import com.example.studentmanagement.entity.Student;
import com.example.studentmanagement.service.StudentService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/students")
public class StudentController {

    @Autowired
    private StudentService studentService;

    /**
     * 新增学生
     */
    @PostMapping
    public Result<Void> addStudent(@RequestBody Student student) {
        studentService.addStudent(student);
        return Result.success();
    }

    /**
     * 根据ID删除学生
     */
    @DeleteMapping("/{id}")
    public Result<Void> deleteStudent(@PathVariable Long id) {
        studentService.deleteStudent(id);
        return Result.success();
    }

    /**
     * 根据ID修改学生信息
     */
    @PutMapping("/{id}")
    public Result<Void> updateStudent(@PathVariable Long id, @RequestBody Student student) {
        student.setId(id);
        studentService.updateStudent(student);
        return Result.success();
    }

    /**
     * 根据ID查询学生详情
     */
    @GetMapping("/{id}")
    public Result<Student> getStudentById(@PathVariable Long id) {
        Student student = studentService.getStudentById(id);
        if (student == null) {
            return Result.error(404, "学生不存在");
        }
        return Result.success(student);
    }

    /**
     * 分页查询学生列表（支持按姓名模糊搜索）
     */
    @GetMapping
    public Result<IPage<Student>> listStudents(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String name) {
        IPage<Student> result = studentService.listStudents(page, pageSize, name);
        return Result.success(result);
    }
}
