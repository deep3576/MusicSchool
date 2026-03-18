CREATE TABLE IF NOT EXISTS teacher_hiring_exam (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT NULL,
  instructions TEXT NULL,
  duration_min INT NOT NULL DEFAULT 45,
  questions_json JSON NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_by_user_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_teacher_hiring_exam_active (is_active),
  CONSTRAINT fk_teacher_hiring_exam_user
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
    ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS teacher_hiring_exam_payment (
  id INT AUTO_INCREMENT PRIMARY KEY,
  exam_id INT NOT NULL,
  full_name VARCHAR(160) NOT NULL,
  email VARCHAR(255) NOT NULL,
  amount_cents INT NOT NULL,
  currency VARCHAR(10) NOT NULL DEFAULT 'usd',
  stripe_session_id VARCHAR(255) NOT NULL,
  stripe_payment_intent_id VARCHAR(255) NULL,
  payment_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  paid_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_teacher_exam_payment_session (stripe_session_id),
  INDEX idx_teacher_exam_payment_exam (exam_id),
  INDEX idx_teacher_exam_payment_email (email),
  CONSTRAINT fk_teacher_hiring_exam_payment_exam
    FOREIGN KEY (exam_id) REFERENCES teacher_hiring_exam(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teacher_hiring_exam_attempt (
  id INT AUTO_INCREMENT PRIMARY KEY,
  exam_id INT NOT NULL,
  full_name VARCHAR(160) NOT NULL,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(60) NULL,
  existing_user_id INT NULL,
  payment_session_id VARCHAR(255) NOT NULL,
  answers_json JSON NOT NULL,
  submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  score DECIMAL(5,2) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'SUBMITTED',
  review_notes TEXT NULL,
  INDEX idx_teacher_exam_attempt_exam (exam_id),
  INDEX idx_teacher_exam_attempt_email (email),
  INDEX idx_teacher_exam_attempt_existing_user (existing_user_id),
  INDEX idx_teacher_exam_attempt_payment_session (payment_session_id),
  INDEX idx_teacher_exam_attempt_submitted_at (submitted_at),
  UNIQUE KEY uq_teacher_exam_attempt_exam_email (exam_id, email),
  CONSTRAINT fk_teacher_hiring_exam_attempt_exam
    FOREIGN KEY (exam_id) REFERENCES teacher_hiring_exam(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_teacher_hiring_exam_attempt_existing_user
    FOREIGN KEY (existing_user_id) REFERENCES user(id)
    ON DELETE SET NULL,
  CONSTRAINT fk_teacher_hiring_exam_attempt_payment
    FOREIGN KEY (payment_session_id) REFERENCES teacher_hiring_exam_payment(stripe_session_id)
    ON DELETE RESTRICT
);
