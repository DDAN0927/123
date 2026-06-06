const initSqlJs = require('sql.js');
const fs = require('fs');
const path = require('path');

const DB_PATH = path.join(__dirname, 'exam_system.db');

async function createDatabase() {
  const SQL = await initSqlJs();

  let db;
  if (fs.existsSync(DB_PATH)) {
    const buffer = fs.readFileSync(DB_PATH);
    db = new SQL.Database(buffer);
  } else {
    db = new SQL.Database();
  }

  db.run(`
    CREATE TABLE IF NOT EXISTS user (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'STUDENT',
      create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS question (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      subject TEXT NOT NULL,
      content TEXT NOT NULL,
      option_a TEXT NOT NULL,
      option_b TEXT NOT NULL,
      option_c TEXT NOT NULL,
      option_d TEXT NOT NULL,
      answer TEXT NOT NULL,
      create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS score (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      username TEXT NOT NULL,
      subject TEXT NOT NULL,
      total_questions INTEGER NOT NULL,
      correct_count INTEGER NOT NULL,
      score INTEGER NOT NULL,
      create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);

  const userCount = db.exec('SELECT COUNT(*) as count FROM user');
  const count = userCount.length > 0 ? userCount[0].values[0][0] : 0;

  if (count === 0) {
    db.run("INSERT INTO user (username, password, role) VALUES ('DDAN', 'admin123', 'ADMIN')");
    db.run("INSERT INTO user (username, password, role) VALUES ('student', '123456', 'STUDENT')");

    const questions = [
      ['Java基础', 'Java中哪个关键字用于定义类？', 'class', 'struct', 'define', 'type', 'A'],
      ['Java基础', 'JDK的全称是什么？', 'Java Development Kit', 'Java Deploy Kit', 'Java Design Kit', 'Java Debug Kit', 'A'],
      ['Java基础', '以下哪个不是Java的基本数据类型？', 'int', 'String', 'boolean', 'double', 'B'],
      ['Java基础', 'Java程序的入口方法签名是？', 'public void main()', 'public static void main(String[] args)', 'static void main()', 'void main(String args)', 'B'],
      ['Java基础', '哪个修饰符表示只有当前类可以访问？', 'public', 'protected', 'default', 'private', 'D'],
      ['数据库', 'SQL中用于查询数据的关键字是？', 'GET', 'SELECT', 'FETCH', 'FIND', 'B'],
      ['数据库', '以下哪个不是SQL的聚合函数？', 'COUNT', 'SUM', 'CONCAT', 'AVG', 'C'],
      ['数据库', 'MySQL中删除表中所有数据但保留表结构的语句是？', 'DROP TABLE', 'DELETE FROM', 'REMOVE TABLE', 'CLEAR TABLE', 'B'],
      ['数据库', '主键的作用是？', '加速查询', '唯一标识记录', '建立索引', '外键关联', 'B'],
      ['数据库', 'HAVING子句通常与哪个子句一起使用？', 'WHERE', 'ORDER BY', 'GROUP BY', 'JOIN', 'C'],
      ['Spring', 'SpringBoot的核心注解是？', '@SpringApplication', '@SpringBoot', '@SpringBootApplication', '@BootApplication', 'C'],
      ['Spring', '@RestController注解等价于？', '@Controller', '@Controller + @ResponseBody', '@Service + @ResponseBody', '@Component + @ResponseBody', 'B'],
      ['Spring', 'Spring中Bean的默认作用域是？', 'prototype', 'request', 'singleton', 'session', 'C'],
      ['Spring', '@Autowired注解的作用是？', '创建Bean', '自动注入依赖', '定义配置', '标记控制器', 'B'],
      ['Spring', 'SpringBoot配置文件的默认名称是？', 'config.xml', 'application.yml/properties', 'spring.json', 'boot.yaml', 'B'],
      ['计算机网络', 'HTTP协议的默认端口号是？', '21', '443', '8080', '80', 'D'],
      ['计算机网络', 'TCP三次握手的正确顺序是？', 'SYN→ACK→FIN', 'SYN→SYN+ACK→ACK', 'ACK→SYN→FIN', 'SYN→FIN→ACK', 'B'],
      ['计算机网络', '以下哪个属于传输层协议？', 'HTTP', 'IP', 'TCP', 'ARP', 'C'],
      ['计算机网络', 'DNS的主要功能是？', '数据加密', '域名解析', '路由转发', '流量控制', 'B'],
      ['计算机网络', 'HTTPS相比HTTP增加了什么？', '速度', '安全性', '端口', '带宽', 'B'],
    ];
    const stmt = db.prepare('INSERT INTO question (subject, content, option_a, option_b, option_c, option_d, answer) VALUES (?, ?, ?, ?, ?, ?, ?)');
    for (const q of questions) {
      stmt.bind(q);
      stmt.step();
      stmt.reset();
    }
    stmt.free();
    console.log('数据库初始化完成，已插入默认用户和题目数据');
  }

  const saveDb = () => {
    const data = db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(DB_PATH, buffer);
  };

  return { db, saveDb };
}

module.exports = { createDatabase };
