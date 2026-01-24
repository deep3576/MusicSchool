CREATE TABLE teacher_class_level (
  teacher_id     INT NOT NULL,
  class_level_id INT NOT NULL,
  is_active      TINYINT(1) NOT NULL DEFAULT 1,
  assigned_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (teacher_id, class_level_id),

  CONSTRAINT fk_tcl_teacher
    FOREIGN KEY (teacher_id) REFERENCES teacher(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_tcl_class_level
    FOREIGN KEY (class_level_id) REFERENCES class_level(id)
    ON DELETE CASCADE,

  KEY idx_tcl_teacher (teacher_id),
  KEY idx_tcl_class_level (class_level_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
