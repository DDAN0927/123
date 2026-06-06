-- 创建数据库
CREATE DATABASE IF NOT EXISTS school_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE school_db;

-- 创建学生表
CREATE TABLE IF NOT EXISTS student (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    name        VARCHAR(50)  NOT NULL                COMMENT '姓名',
    age         INT                                  COMMENT '年龄',
    email       VARCHAR(100)                         COMMENT '邮箱',
    create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生信息表';
