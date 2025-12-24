ALTER TABLE teacher
  ADD COLUMN shift_start_time TIME,
  ADD COLUMN shift_end_time   TIME,
  ADD COLUMN break_start_time TIME,
  ADD COLUMN break_end_time   TIME;


ALTER TABLE teacher_availability
    ADD COLUMN businessdate Date;

-- releases/20251223_add_assigned_class_to_user.sql

ALTER TABLE `user`
  ADD COLUMN assigned_class_id INT NULL;

CREATE INDEX idx_user_assigned_class_id ON `user`(assigned_class_id);

-- Optional FK (only if you want strict integrity; skip if you prefer flexibility)
-- ALTER TABLE `user`
--   ADD CONSTRAINT fk_user_assigned_class
--   FOREIGN KEY (assigned_class_id) REFERENCES class_level(id)
--   ON DELETE SET NULL
--   ON UPDATE CASCADE;
