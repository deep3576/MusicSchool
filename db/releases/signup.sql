/* =========================================================
   TheSpiritSchool.ca - Release 003 (Users + Roles + Profile)
   Adds:
   - user.role (admin/student/teacher)
   - user profile fields (name, phone, address)
   - booking.user_id FK to user (for student bookings)
   ========================================================= */

USE `deep3576$TheSpiritSchool_ProdDB`;
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- ---------- helper: add column if missing ----------
SET @db := DATABASE();

-- role
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='role');
SET @sql := IF(@exists=0,
    "ALTER TABLE `user` ADD COLUMN `role` varchar(20) NOT NULL DEFAULT 'student' CHECK (role IN ('student','teacher','admin')) AFTER `password_hash`",
  "SELECT 'user.role exists'");

  'role' TEXT NOT NULL DEFAULT 'student'
    CHECK (role IN ('student','teacher','admin'))

PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- first_name
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='first_name');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `first_name` VARCHAR(80) NULL AFTER `role`",
  "SELECT 'user.first_name exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- last_name
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='last_name');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `last_name` VARCHAR(80) NULL AFTER `first_name`",
  "SELECT 'user.last_name exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- phone
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='phone');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `phone` VARCHAR(60) NULL AFTER `last_name`",
  "SELECT 'user.phone exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- address_1
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='address_1');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `address_1` VARCHAR(200) NULL AFTER `phone`",
  "SELECT 'user.address_1 exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- address_2
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='address_2');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `address_2` VARCHAR(200) NULL AFTER `address_1`",
  "SELECT 'user.address_2 exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- city
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='city');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `city` VARCHAR(120) NULL AFTER `address_2`",
  "SELECT 'user.city exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- province
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='province');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `province` VARCHAR(120) NULL AFTER `city`",
  "SELECT 'user.province exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- postal_code
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='postal_code');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `postal_code` VARCHAR(30) NULL AFTER `province`",
  "SELECT 'user.postal_code exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- country
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND COLUMN_NAME='country');
SET @sql := IF(@exists=0,
  "ALTER TABLE `user` ADD COLUMN `country` VARCHAR(80) NULL AFTER `postal_code`",
  "SELECT 'user.country exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- index role
SET @exists := (SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='user' AND INDEX_NAME='ix_user_role');
SET @sql := IF(@exists=0,
  "CREATE INDEX `ix_user_role` ON `user`(`role`)",
  "SELECT 'ix_user_role exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ---------- booking.user_id ----------
SET @exists := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='booking' AND COLUMN_NAME='user_id');
SET @sql := IF(@exists=0,
  "ALTER TABLE `booking` ADD COLUMN `user_id` INT NULL AFTER `availability_id`",
  "SELECT 'booking.user_id exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- index user_id
SET @exists := (SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='booking' AND INDEX_NAME='ix_booking_user_id');
SET @sql := IF(@exists=0,
  "CREATE INDEX `ix_booking_user_id` ON `booking`(`user_id`)",
  "SELECT 'ix_booking_user_id exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- FK booking.user_id -> user.id (add if missing)
SET @exists := (
  SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE
  WHERE TABLE_SCHEMA=@db AND TABLE_NAME='booking' AND COLUMN_NAME='user_id'
    AND REFERENCED_TABLE_NAME='user'
);
SET @sql := IF(@exists=0,
  "ALTER TABLE `booking` ADD CONSTRAINT `fk_booking_user` FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE SET NULL",
  "SELECT 'fk_booking_user exists'");
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ---------- IMPORTANT: promote your admin email ----------
-- Change email below if your admin is different:
UPDATE `user`
SET `role`='admin'
WHERE `email`='admin@therhythmschool.ca';
