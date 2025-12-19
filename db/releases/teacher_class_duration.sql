USE `deep3576$TheSpiritSchool_ProdDB`;
SET NAMES utf8mb4;

SET @db := DATABASE();
SET @exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='teacher' AND COLUMN_NAME='class_duration_min'
);

SET @sql := IF(
  @exists=0,
  "ALTER TABLE `teacher` ADD COLUMN `class_duration_min` INT NOT NULL DEFAULT 45 AFTER `bio`",
  "SELECT 'teacher.class_duration_min exists'"
);

PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
