const express = require('express');
const cors = require('cors');
const jwt = require('jsonwebtoken');
const path = require('path');
const { createDatabase } = require('./database');

const SECRET = 'exam-system-jwt-secret-key-2024';

async function startServer() {
  const { db, saveDb } = await createDatabase();

  const app = express();
  app.use(cors());
  app.use(express.json());
  app.use(express.static(path.join(__dirname, '../exam-system-frontend/dist')));

  function authMiddleware(req, res, next) {
    const authHeader = req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res.status(401).json({ code: 401, msg: '未登录，请先登录' });
    }
    try {
      const token = authHeader.replace('Bearer ', '');
      req.user = jwt.verify(token, SECRET);
      next();
    } catch (e) {
      return res.status(401).json({ code: 401, msg: 'Token无效或已过期，请重新登录' });
    }
  }

  function adminMiddleware(req, res, next) {
    if (req.user.role !== 'ADMIN') {
      return res.status(403).json({ code: 403, msg: '无权限访问' });
    }
    next();
  }

  function queryAll(sql, params = []) {
    const stmt = db.prepare(sql);
    stmt.bind(params);
    const rows = [];
    while (stmt.step()) {
      const obj = stmt.getAsObject();
      if (obj.option_a !== undefined) {
        obj.optionA = obj.option_a;
        obj.optionB = obj.option_b;
        obj.optionC = obj.option_c;
        obj.optionD = obj.option_d;
        delete obj.option_a;
        delete obj.option_b;
        delete obj.option_c;
        delete obj.option_d;
      }
      rows.push(obj);
    }
    stmt.free();
    return rows;
  }

  function queryOne(sql, params = []) {
    const rows = queryAll(sql, params);
    return rows.length > 0 ? rows[0] : null;
  }

  function runSql(sql, params = []) {
    db.run(sql, params);
    saveDb();
  }

  app.post('/api/user/login', (req, res) => {
    const { username, password } = req.body;
    const user = queryOne('SELECT * FROM user WHERE username = ?', [username]);
    if (!user) return res.json({ code: 500, msg: '用户不存在' });
    if (user.password !== password) return res.json({ code: 500, msg: '密码错误' });
    const token = jwt.sign(
      { userId: user.id, username: user.username, role: user.role },
      SECRET,
      { expiresIn: '24h' }
    );
    res.json({ code: 200, msg: '操作成功', data: { token, username: user.username, role: user.role } });
  });

  app.post('/api/user/register', (req, res) => {
    const { username, password } = req.body;
    const exist = queryOne('SELECT * FROM user WHERE username = ?', [username]);
    if (exist) return res.json({ code: 500, msg: '用户名已存在' });
    runSql('INSERT INTO user (username, password, role) VALUES (?, ?, ?)', [username, password, 'STUDENT']);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.get('/api/user/list', authMiddleware, adminMiddleware, (req, res) => {
    const { pageNum = 1, pageSize = 10, username, role } = req.query;
    const offset = (pageNum - 1) * pageSize;
    let countSql = 'SELECT COUNT(*) as total FROM user';
    let listSql = 'SELECT id, username, role, create_time FROM user';
    const conditions = [];
    const params = [];
    if (username) {
      conditions.push('username LIKE ?');
      params.push(`%${username}%`);
    }
    if (role) {
      conditions.push('role = ?');
      params.push(role);
    }
    if (conditions.length > 0) {
      const where = ' WHERE ' + conditions.join(' AND ');
      countSql += where;
      listSql += where;
    }
    listSql += ' ORDER BY id DESC LIMIT ? OFFSET ?';
    const total = queryOne(countSql, params).total;
    const list = queryAll(listSql, [...params, Number(pageSize), Number(offset)]);
    res.json({ code: 200, msg: '操作成功', data: { list, total, pageNum: Number(pageNum), pageSize: Number(pageSize) } });
  });

  app.post('/api/user/add', authMiddleware, adminMiddleware, (req, res) => {
    const { username, password, role } = req.body;
    const exist = queryOne('SELECT * FROM user WHERE username = ?', [username]);
    if (exist) return res.json({ code: 500, msg: '用户名已存在' });
    runSql('INSERT INTO user (username, password, role) VALUES (?, ?, ?)', [username, password, role || 'STUDENT']);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.put('/api/user/reset-password', authMiddleware, adminMiddleware, (req, res) => {
    const { id, password } = req.body;
    const user = queryOne('SELECT * FROM user WHERE id = ?', [id]);
    if (!user) return res.json({ code: 500, msg: '用户不存在' });
    runSql('UPDATE user SET password = ? WHERE id = ?', [password, id]);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.delete('/api/user/:id', authMiddleware, adminMiddleware, (req, res) => {
    const user = queryOne('SELECT * FROM user WHERE id = ?', [req.params.id]);
    if (!user) return res.json({ code: 500, msg: '用户不存在' });
    if (user.role === 'ADMIN') return res.json({ code: 500, msg: '不能删除管理员账号' });
    runSql('DELETE FROM user WHERE id = ?', [req.params.id]);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.get('/api/question/list', (req, res) => {
    const { pageNum = 1, pageSize = 10, subject } = req.query;
    const offset = (pageNum - 1) * pageSize;
    let countSql = 'SELECT COUNT(*) as total FROM question';
    let listSql = 'SELECT * FROM question';
    const params = [];
    if (subject) {
      countSql += ' WHERE subject = ?';
      listSql += ' WHERE subject = ?';
      params.push(subject);
    }
    listSql += ' ORDER BY id DESC LIMIT ? OFFSET ?';
    const total = queryOne(countSql, params).total;
    const list = queryAll(listSql, [...params, Number(pageSize), Number(offset)]);
    res.json({ code: 200, msg: '操作成功', data: { list, total, pageNum: Number(pageNum), pageSize: Number(pageSize) } });
  });

  app.get('/api/question/random', (req, res) => {
    const { subject, count = 10 } = req.query;
    const list = queryAll('SELECT * FROM question WHERE subject = ? ORDER BY RANDOM() LIMIT ?', [subject, Number(count)]);
    res.json({ code: 200, msg: '操作成功', data: list });
  });

  app.get('/api/question/:id', authMiddleware, (req, res) => {
    const question = queryOne('SELECT * FROM question WHERE id = ?', [req.params.id]);
    res.json({ code: 200, msg: '操作成功', data: question });
  });

  app.post('/api/question', authMiddleware, adminMiddleware, (req, res) => {
    const { subject, content, optionA, optionB, optionC, optionD, answer } = req.body;
    runSql('INSERT INTO question (subject, content, option_a, option_b, option_c, option_d, answer) VALUES (?, ?, ?, ?, ?, ?, ?)',
      [subject, content, optionA, optionB, optionC, optionD, answer]);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.put('/api/question', authMiddleware, adminMiddleware, (req, res) => {
    const { id, subject, content, optionA, optionB, optionC, optionD, answer } = req.body;
    runSql('UPDATE question SET subject=?, content=?, option_a=?, option_b=?, option_c=?, option_d=?, answer=? WHERE id=?',
      [subject, content, optionA, optionB, optionC, optionD, answer, id]);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.delete('/api/question/:id', authMiddleware, adminMiddleware, (req, res) => {
    runSql('DELETE FROM question WHERE id = ?', [req.params.id]);
    res.json({ code: 200, msg: '操作成功' });
  });

  app.get('/api/score/list', authMiddleware, adminMiddleware, (req, res) => {
    const { pageNum = 1, pageSize = 10, username, subject } = req.query;
    const offset = (pageNum - 1) * pageSize;
    let countSql = 'SELECT COUNT(*) as total FROM score';
    let listSql = 'SELECT * FROM score';
    const conditions = [];
    const params = [];
    if (username) {
      conditions.push('username LIKE ?');
      params.push(`%${username}%`);
    }
    if (subject) {
      conditions.push('subject = ?');
      params.push(subject);
    }
    if (conditions.length > 0) {
      const where = ' WHERE ' + conditions.join(' AND ');
      countSql += where;
      listSql += where;
    }
    listSql += ' ORDER BY id DESC LIMIT ? OFFSET ?';
    const total = queryOne(countSql, params).total;
    const list = queryAll(listSql, [...params, Number(pageSize), Number(offset)]);
    res.json({ code: 200, msg: '操作成功', data: { list, total, pageNum: Number(pageNum), pageSize: Number(pageSize) } });
  });

  app.get('/api/score/my', authMiddleware, (req, res) => {
    const { pageNum = 1, pageSize = 10 } = req.query;
    const offset = (pageNum - 1) * pageSize;
    const total = queryOne('SELECT COUNT(*) as total FROM score WHERE user_id = ?', [req.user.userId]).total;
    const list = queryAll('SELECT * FROM score WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?',
      [req.user.userId, Number(pageSize), Number(offset)]);
    res.json({ code: 200, msg: '操作成功', data: { list, total, pageNum: Number(pageNum), pageSize: Number(pageSize) } });
  });

  app.post('/api/score/submit', authMiddleware, (req, res) => {
    const { subject, answers } = req.body;
    let correctCount = 0;
    for (const a of answers) {
      const q = queryOne('SELECT * FROM question WHERE id = ?', [Number(a.questionId)]);
      if (q && q.answer === a.answer) correctCount++;
    }
    const totalQuestions = answers.length;
    const scoreValue = Math.round((correctCount * 100) / totalQuestions);
    runSql('INSERT INTO score (user_id, username, subject, total_questions, correct_count, score) VALUES (?, ?, ?, ?, ?, ?)',
      [req.user.userId, req.user.username, subject, totalQuestions, correctCount, scoreValue]);
    res.json({
      code: 200, msg: '操作成功',
      data: { userId: req.user.userId, username: req.user.username, subject, totalQuestions, correctCount, score: scoreValue }
    });
  });

  app.get('*', (req, res, next) => {
    if (req.path.startsWith('/api/')) {
      return res.status(404).json({ code: 404, msg: '接口不存在' });
    }
    res.sendFile(path.join(__dirname, '../exam-system-frontend/dist/index.html'));
  });

  const PORT = 8088;
  const HOST = '0.0.0.0';
  app.listen(PORT, HOST, () => {
    console.log(`考试系统后端已启动: http://localhost:${PORT}`);
    console.log('默认账号: DDAN/admin123 (管理员), student/123456 (学生)');
  });
}

startServer().catch(err => {
  console.error('启动失败:', err);
  process.exit(1);
});
