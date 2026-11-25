-- ============================================================================
--  个人旅游智能管理系统 · MySQL 建库脚本
--
--  用途：答辩/部署时用 MySQL 起库（任务书 1(2) 要求 MySQL）。
--  用法：
--    mysql -uroot -p < schema-mysql.sql
--    然后启动时加 --spring.profiles.active=mysql
--  说明：
--    * 表名、列名与 JPA 实体完全一致（Spring 默认驼峰转下划线），
--      所以 ddl-auto=update 不会再改结构；本脚本可以放心当唯一真相。
--    * 金额统一 DECIMAL(10,2)，不要用 FLOAT：0.1+0.2 在浮点里不等于 0.3，
--      记账系统里这种误差会被用户当成 bug。
--    * 字符集 utf8mb4：景点名里有生僻字与 emoji，utf8 存不下。
-- ============================================================================

CREATE DATABASE IF NOT EXISTS travel
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE travel;

-- ---------------------------------------------------------------- 用户表
CREATE TABLE IF NOT EXISTS users (
  id                  BIGINT       NOT NULL AUTO_INCREMENT,
  username            VARCHAR(40)  NOT NULL COMMENT '登录名，3-20 位字母数字下划线或汉字',
  password_hash       VARCHAR(100) NOT NULL COMMENT 'BCrypt 哈希，永不返回前端',
  role                VARCHAR(16)  NOT NULL DEFAULT 'user' COMMENT 'user / admin',
  created_at          DATETIME(6)  NOT NULL,
  password_changed_at DATETIME(6)  NULL COMMENT '仅审计展示，不用于 token 失效判断',
  token_epoch         BIGINT       NULL COMMENT '会话世代：改密 +1，旧 token 立即失效',
  preference_tags     VARCHAR(200) NULL COMMENT '偏好标签，逗号分隔，最多 8 个',
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户';

-- ---------------------------------------------------------------- 景点表
CREATE TABLE IF NOT EXISTS spots (
  id              BIGINT        NOT NULL AUTO_INCREMENT,
  city            VARCHAR(40)   NOT NULL COMMENT '所属城市',
  name            VARCHAR(120)  NOT NULL COMMENT '景点名',
  category        VARCHAR(20)   NULL COMMENT '地标/公园/古迹/场馆/亲子/街区/自然/美食',
  tags            VARCHAR(200)  NULL COMMENT '标签，逗号分隔：室内/室外/免费/亲子/拍照/历史/夜游/少走路',
  ticket_price    DECIMAL(10,2) NULL COMMENT '门票（元）。NULL=未录入，0=免费，两者含义不同',
  suggest_minutes INT           NULL COMMENT '建议游玩时长（分钟）',
  address         VARCHAR(200)  NULL,
  lng             DOUBLE        NULL,
  lat             DOUBLE        NULL,
  rating          VARCHAR(10)   NULL COMMENT '平台评分，保留一位小数原样',
  open_time       VARCHAR(40)   NULL COMMENT '开放时间文本，如 08:30-17:00 / 24小时营业',
  source          VARCHAR(20)   NOT NULL DEFAULT 'manual' COMMENT 'amap=快照导入 / manual=后台录入',
  created_at      DATETIME(6)   NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_spots_city_name (city, name),
  KEY idx_spots_city (city),
  KEY idx_spots_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='景点库';

-- ---------------------------------------------------------------- 行程表
CREATE TABLE IF NOT EXISTS trips (
  id          VARCHAR(32) NOT NULL COMMENT '12 位十六进制，前端会拼进 URL',
  username    VARCHAR(40) NOT NULL COMMENT '所属用户',
  city        VARCHAR(40) NOT NULL COMMENT '目的地',
  title       VARCHAR(80) NOT NULL,
  start_date  DATE        NULL COMMENT '出发日期，可为空（未定日期）',
  days        INT         NOT NULL DEFAULT 3,
  budget      INT         NOT NULL DEFAULT 0 COMMENT '人均预算（元），0=未设置',
  note        VARCHAR(500) NULL,
  share_token VARCHAR(40) NULL COMMENT '分享令牌，非空即可只读访问，随时可作废',
  created_at  DATETIME(6) NOT NULL,
  updated_at  DATETIME(6) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_trips_share (share_token),
  KEY idx_trips_user (username),
  CONSTRAINT fk_trips_user FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程';

-- ---------------------------------------------------------------- 行程明细表
CREATE TABLE IF NOT EXISTS trip_items (
  id        BIGINT       NOT NULL AUTO_INCREMENT,
  trip_id   VARCHAR(32)  NOT NULL,
  day_index INT          NOT NULL COMMENT '0=行前清单，1..N=第 N 天',
  slot      VARCHAR(20)  NULL COMMENT '上午/下午/晚上；行前清单里当分组名',
  kind      VARCHAR(20)  NOT NULL DEFAULT 'spot' COMMENT 'spot/food/stay/transit/experience/packing/doc',
  title     VARCHAR(120) NOT NULL,
  note      VARCHAR(500) NULL,
  done      TINYINT(1)   NOT NULL DEFAULT 0,
  sort      INT          NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_items_trip (trip_id, day_index, sort),
  CONSTRAINT fk_items_trip FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行程明细（行程-景点一对多）';

-- ---------------------------------------------------------------- 费用表
CREATE TABLE IF NOT EXISTS trip_expenses (
  id         BIGINT        NOT NULL AUTO_INCREMENT,
  trip_id    VARCHAR(32)   NOT NULL,
  category   VARCHAR(20)   NOT NULL DEFAULT '其他' COMMENT '交通/住宿/餐饮/门票/购物/其他',
  title      VARCHAR(120)  NOT NULL,
  amount     DECIMAL(10,2) NOT NULL,
  day_index  INT           NOT NULL DEFAULT 0 COMMENT '0=行前支出',
  spent_on   DATE          NULL,
  created_at DATETIME(6)   NOT NULL,
  PRIMARY KEY (id),
  KEY idx_exp_trip (trip_id, spent_on),
  KEY idx_exp_category (category),
  CONSTRAINT fk_exp_trip FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='费用记账';

-- ---------------------------------------------------------------- 游记表
CREATE TABLE IF NOT EXISTS trip_notes (
  id         BIGINT       NOT NULL AUTO_INCREMENT,
  trip_id    VARCHAR(32)  NOT NULL,
  username   VARCHAR(40)  NOT NULL,
  title      VARCHAR(80)  NOT NULL,
  content    LONGTEXT     NOT NULL COMMENT '正文，图文混排的纯文本',
  images     VARCHAR(1000) NULL COMMENT '逗号分隔的图片地址 /api/uploads/xxx.jpg',
  created_at DATETIME(6)  NOT NULL,
  updated_at DATETIME(6)  NOT NULL,
  PRIMARY KEY (id),
  KEY idx_note_trip (trip_id, created_at),
  CONSTRAINT fk_note_trip FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游记';

-- ---------------------------------------------------------------- 初始化管理员
-- 密码哈希由应用启动时写入（SeedDataConfig），这里不写死明文密码。
-- 若手工插入，password_hash 必须是 BCrypt 串，不能用明文。
