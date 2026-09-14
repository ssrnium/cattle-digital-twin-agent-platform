-- 单牛数字孪生与健康繁殖任务管理平台 - PostgreSQL 建库脚本
-- 验收关键点：unified_event.event_id 唯一约束（幂等去重的最后防线）、work_order.order_no 唯一

CREATE TABLE IF NOT EXISTS sys_user (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL,
    password      VARCHAR(128) NOT NULL,
    nickname      VARCHAR(64),
    phone         VARCHAR(32),
    status        VARCHAR(16)  NOT NULL DEFAULT 'ENABLED',
    create_time   TIMESTAMP    NOT NULL DEFAULT now(),
    update_time   TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sys_user_username ON sys_user(username);

CREATE TABLE IF NOT EXISTS sys_role (
    id          BIGSERIAL PRIMARY KEY,
    role_code   VARCHAR(64) NOT NULL,
    role_name   VARCHAR(64) NOT NULL,
    description VARCHAR(255),
    create_time TIMESTAMP NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sys_role_code ON sys_role(role_code);

CREATE TABLE IF NOT EXISTS sys_user_role (
    id      BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sys_user_role ON sys_user_role(user_id, role_id);

CREATE TABLE IF NOT EXISTS sys_role_perm (
    id        BIGSERIAL PRIMARY KEY,
    role_id   BIGINT       NOT NULL,
    perm_code VARCHAR(128) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_sys_role_perm ON sys_role_perm(role_id, perm_code);

CREATE TABLE IF NOT EXISTS sys_operation_log (
    id           BIGSERIAL PRIMARY KEY,
    title        VARCHAR(128),
    username     VARCHAR(64),
    method       VARCHAR(255),
    request_uri  VARCHAR(255),
    request_ip   VARCHAR(64),
    params       TEXT,
    status       VARCHAR(16),
    error_msg    TEXT,
    operate_time TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cow_profile (
    id          BIGSERIAL PRIMARY KEY,
    cow_id      VARCHAR(32) NOT NULL,
    ear_tag     VARCHAR(64),
    barn_id     VARCHAR(64) NOT NULL DEFAULT '20号牛棚',
    zone        VARCHAR(16),
    status      VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    create_time TIMESTAMP   NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_cow_profile_cow_id ON cow_profile(cow_id);

CREATE TABLE IF NOT EXISTS cow_timeline (
    id           BIGSERIAL PRIMARY KEY,
    cow_id       VARCHAR(32)  NOT NULL,
    event_id     VARCHAR(64),
    event_type   VARCHAR(32)  NOT NULL,
    title        VARCHAR(255),
    detail       JSONB,
    state_nature VARCHAR(16)  NOT NULL DEFAULT 'INFERRED', -- MEASURED / INFERRED / MANUAL
    event_time   TIMESTAMP    NOT NULL,
    create_time  TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cow_timeline_cow ON cow_timeline(cow_id, event_time DESC);

CREATE TABLE IF NOT EXISTS twin_state (
    cow_id          VARCHAR(32) PRIMARY KEY,
    state           JSONB       NOT NULL DEFAULT '{}'::jsonb, -- posture/zone/health_status/estrus_status ...
    state_nature    VARCHAR(16) NOT NULL DEFAULT 'INFERRED',
    source_event_id VARCHAR(64),
    event_time      TIMESTAMP,
    version         INT         NOT NULL DEFAULT 0, -- 乐观锁
    updated_at      TIMESTAMP   NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS unified_event (
    id             BIGSERIAL PRIMARY KEY,
    schema_version VARCHAR(16)  NOT NULL,
    tenant_id      VARCHAR(32)  NOT NULL DEFAULT 'default',
    farm_id        VARCHAR(32),
    event_id       VARCHAR(64)  NOT NULL,            -- 全局唯一，幂等去重键
    cow_id         VARCHAR(32),
    device_id      VARCHAR(64),
    event_type     VARCHAR(32)  NOT NULL,            -- MOUNTING/LAMENESS/DEVICE_OFFLINE/DEVICE_RECOVERED/SYNC_STATE
    event_time     TIMESTAMP    NOT NULL,
    ingest_time    TIMESTAMP    NOT NULL DEFAULT now(),
    quality        VARCHAR(16),
    confidence     DOUBLE PRECISION,
    model_version  VARCHAR(64),
    evidence_ref   VARCHAR(512),
    raw            JSONB
);
-- 幂等去重的数据库级保障：重复 event_id 插入必冲突
CREATE UNIQUE INDEX IF NOT EXISTS uk_unified_event_event_id ON unified_event(event_id);
CREATE INDEX IF NOT EXISTS idx_unified_event_type_time ON unified_event(event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_unified_event_cow ON unified_event(cow_id, event_time DESC);

CREATE TABLE IF NOT EXISTS work_order (
    id              BIGSERIAL PRIMARY KEY,
    order_no        VARCHAR(40)  NOT NULL,
    type            VARCHAR(32)  NOT NULL, -- BREEDING_REVIEW/VET_CHECK/DEVICE_REPAIR
    cow_id          VARCHAR(32),
    device_id       VARCHAR(64),
    source_event_id VARCHAR(64),
    state           VARCHAR(24)  NOT NULL DEFAULT 'NEW', -- NEW/DISPATCHED/PROCESSING/PENDING_REVIEW/CLOSED/CANCELLED
    priority        VARCHAR(16)  NOT NULL DEFAULT 'NORMAL',
    assignee_id     BIGINT,
    description     TEXT,
    review_result   TEXT,
    reviewed_by     VARCHAR(64),
    reviewed_at     TIMESTAMP,
    version         INT          NOT NULL DEFAULT 0, -- 乐观锁：禁止 last-write-wins
    create_time     TIMESTAMP    NOT NULL DEFAULT now(),
    update_time     TIMESTAMP    NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_work_order_order_no ON work_order(order_no);
CREATE INDEX IF NOT EXISTS idx_work_order_state ON work_order(state, type);
CREATE INDEX IF NOT EXISTS idx_work_order_cow ON work_order(cow_id, type, state);

CREATE TABLE IF NOT EXISTS device (
    id               BIGSERIAL PRIMARY KEY,
    device_id        VARCHAR(64) NOT NULL,
    device_key       VARCHAR(128) NOT NULL, -- 设备凭证（心跳/HTTP 上报校验用）
    type             VARCHAR(16) NOT NULL,  -- CAMERA/EDGE_NODE
    name             VARCHAR(128),
    barn_id          VARCHAR(64),
    last_heartbeat_at TIMESTAMP,
    last_sync_at     TIMESTAMP,
    pending_count    INT NOT NULL DEFAULT 0,
    meta             JSONB
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_device_device_id ON device(device_id);

-- ============ 牧场智能体（cow-agent）会话审计 ============
CREATE TABLE IF NOT EXISTS agent_session (
    id               BIGSERIAL PRIMARY KEY,
    session_id       VARCHAR(32) NOT NULL,
    username         VARCHAR(64) NOT NULL, -- 发起对话的业务账号
    create_time      TIMESTAMP   NOT NULL DEFAULT now(),
    last_active_time TIMESTAMP   NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_agent_session_sid ON agent_session(session_id);

CREATE TABLE IF NOT EXISTS agent_message (
    id            BIGSERIAL PRIMARY KEY,
    session_id    VARCHAR(32) NOT NULL,
    role          VARCHAR(16) NOT NULL, -- user / assistant
    content       TEXT,
    tokens_input  INT,
    tokens_output INT,
    create_time   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_message_session ON agent_message(session_id, id);
