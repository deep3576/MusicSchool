
-- 1) USERS & PROFILES ---------------------------------------------------------

CREATE TABLE users (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  role              ENUM('customer','contractor','admin') NOT NULL,
  email             VARCHAR(255) NOT NULL UNIQUE,
  phone             VARCHAR(32),
  password_hash     VARCHAR(255) NOT NULL,          -- bcrypt/argon2; NEVER store plaintext
  first_name        VARCHAR(80) NOT NULL,
  last_name         VARCHAR(80) NOT NULL,
  is_active         TINYINT(1) NOT NULL DEFAULT 1,
  last_login_at     DATETIME(6) NULL,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  INDEX idx_users_role (role),
  INDEX idx_users_created (created_at)
) ENGINE=InnoDB;

-- Optional: richer customer profile
CREATE TABLE customer_profile (
  user_id           BIGINT UNSIGNED PRIMARY KEY,
  address_line1     VARCHAR(160),
  address_line2     VARCHAR(160),
  city              VARCHAR(90),
  province          VARCHAR(90),
  postal_code       VARCHAR(20),
  preferred_contact ENUM('phone','email','sms') DEFAULT 'email',
  notes             TEXT,
  CONSTRAINT fk_custprof_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Optional: contractor profile
CREATE TABLE contractor_profile (
  user_id           BIGINT UNSIGNED PRIMARY KEY,
  company_name      VARCHAR(160),
  trade             VARCHAR(120),     -- e.g., GC, Electrical, Plumbing, HVAC
  wsib_number       VARCHAR(64),
  insurance_policy  VARCHAR(64),
  notes             TEXT,
  CONSTRAINT fk_contractor_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 2) JOBS & ACCESS CONTROL ----------------------------------------------------

CREATE TABLE jobs (
  id                        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_uid                   CHAR(12) NOT NULL UNIQUE,     -- public-facing unique ID (e.g., KMSA12B34C56)
  customer_user_id          BIGINT UNSIGNED NOT NULL,     -- the owner/customer for access control
  assigned_contractor_user_id BIGINT UNSIGNED NULL,       -- main contractor (can be NULL initially)
  title                     VARCHAR(160) NOT NULL,
  description               TEXT,
  site_address_line1        VARCHAR(160),
  site_address_line2        VARCHAR(160),
  site_city                 VARCHAR(90),
  site_province             VARCHAR(90),
  site_postal_code          VARCHAR(20),
  status                    ENUM('new','design','permit','in_progress','inspection','completed','on_hold','cancelled')
                               NOT NULL DEFAULT 'new',
  percent_complete          DECIMAL(5,2) NOT NULL DEFAULT 0.00, -- 0–100.00
  budget_estimate_cad       DECIMAL(12,2) NULL,
  start_date                DATE NULL,
  target_completion_date    DATE NULL,
  completed_at              DATETIME(6) NULL,
  created_by_user_id        BIGINT UNSIGNED NOT NULL,
  created_at                DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at                DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_jobs_customer    FOREIGN KEY (customer_user_id) REFERENCES users(id),
  CONSTRAINT fk_jobs_contractor  FOREIGN KEY (assigned_contractor_user_id) REFERENCES users(id),
  CONSTRAINT fk_jobs_created_by  FOREIGN KEY (created_by_user_id) REFERENCES users(id),
  INDEX idx_jobs_customer (customer_user_id),
  INDEX idx_jobs_contractor (assigned_contractor_user_id),
  INDEX idx_jobs_status (status, updated_at),
  INDEX idx_jobs_created (created_at)
) ENGINE=InnoDB;

-- (Optional) If you ever need to grant additional customer viewers to a job:
CREATE TABLE job_access (
  job_id            BIGINT UNSIGNED NOT NULL,
  user_id           BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (job_id, user_id),
  CONSTRAINT fk_jobaccess_job  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_jobaccess_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 3) JOB STATUS HISTORY, UPDATES & DOCUMENTS ---------------------------------

CREATE TABLE job_status_history (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_id            BIGINT UNSIGNED NOT NULL,
  old_status        ENUM('new','design','permit','in_progress','inspection','completed','on_hold','cancelled') NULL,
  new_status        ENUM('new','design','permit','in_progress','inspection','completed','on_hold','cancelled') NOT NULL,
  note              VARCHAR(500),
  changed_by_user_id BIGINT UNSIGNED NOT NULL,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_jstat_job   FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_jstat_user  FOREIGN KEY (changed_by_user_id) REFERENCES users(id),
  INDEX idx_jstat_job_created (job_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE job_updates (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_id            BIGINT UNSIGNED NOT NULL,
  posted_by_user_id BIGINT UNSIGNED NOT NULL,
  visibility        ENUM('customer','internal','both') NOT NULL DEFAULT 'customer',
  message           TEXT,
  percent_complete  DECIMAL(5,2) NULL,       -- optional quick progress mark
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_jupd_job   FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_jupd_user  FOREIGN KEY (posted_by_user_id) REFERENCES users(id),
  INDEX idx_jupd_job_created (job_id, created_at),
  INDEX idx_jupd_visibility (visibility)
) ENGINE=InnoDB;

CREATE TABLE job_attachments (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_id            BIGINT UNSIGNED NOT NULL,
  uploaded_by_user_id BIGINT UNSIGNED NOT NULL,
  category          ENUM('photo','document','permit','design','invoice','inspection','other') NOT NULL DEFAULT 'document',
  file_name         VARCHAR(255) NOT NULL,
  mime_type         VARCHAR(120),
  storage_url       VARCHAR(1024) NOT NULL,   -- S3/Cloud storage location
  size_bytes        BIGINT UNSIGNED,
  is_visible_to_customer TINYINT(1) NOT NULL DEFAULT 1,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_jatt_job   FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_jatt_user  FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id),
  INDEX idx_jatt_job (job_id, category, created_at)
) ENGINE=InnoDB;

-- 4) FEEDBACK ----------------------------------------------------------------

CREATE TABLE job_feedback (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  job_id            BIGINT UNSIGNED NOT NULL,
  customer_user_id  BIGINT UNSIGNED NOT NULL,
  rating            TINYINT UNSIGNED NOT NULL CHECK (rating BETWEEN 1 AND 5),
  would_recommend   TINYINT(1) NOT NULL DEFAULT 1,
  comments          TEXT,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_jfb_job   FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
  CONSTRAINT fk_jfb_user  FOREIGN KEY (customer_user_id) REFERENCES users(id),
  UNIQUE KEY uq_feedback_job_customer (job_id, customer_user_id)
) ENGINE=InnoDB;

-- 5) LOGIN / LOGOUT AUDIT ----------------------------------------------------

CREATE TABLE auth_login_audit (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id           BIGINT UNSIGNED NOT NULL,
  action            ENUM('login','logout') NOT NULL,
  success           TINYINT(1) NOT NULL DEFAULT 1,   -- for login attempts
  ip_address        VARCHAR(45),                     -- IPv4/IPv6
  user_agent        VARCHAR(255),
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_log_user FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX idx_log_user_created (user_id, created_at),
  INDEX idx_log_action (action, created_at)
) ENGINE=InnoDB;

-- 6) OPTIONAL: PASSWORD RESET TOKENS -----------------------------------------

CREATE TABLE auth_password_resets (
  id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id           BIGINT UNSIGNED NOT NULL,
  token_hash        VARBINARY(64) NOT NULL,          -- store SHA-256 of token
  expires_at        DATETIME(6) NOT NULL,
  used_at           DATETIME(6) NULL,
  created_at        DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  CONSTRAINT fk_pw_user FOREIGN KEY (user_id) REFERENCES users(id),
  UNIQUE KEY uq_pw_token (token_hash)
) ENGINE=InnoDB;
