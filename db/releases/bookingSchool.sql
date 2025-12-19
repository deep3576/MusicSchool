/* =========================================================
   TheSpiritSchool.ca - Release 002 (Music School + Booking)
   Database: deep3576$TheSpiritSchool_ProdDB
   ========================================================= */

USE `deep3576$TheSpiritSchool_ProdDB`;

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- 1) Extend contact_message for replies
ALTER TABLE `contact_message`
  ADD COLUMN IF NOT EXISTS `reply_subject` VARCHAR(200) NULL,
  ADD COLUMN IF NOT EXISTS `reply_body` TEXT NULL,
  ADD COLUMN IF NOT EXISTS `replied_at` DATETIME NULL;

-- 2) Class Levels (1M..10M)
CREATE TABLE IF NOT EXISTS `class_level` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(10) NOT NULL,         -- 1M..10M
  `title` VARCHAR(120) NOT NULL,       -- display name
  `description` TEXT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_class_level_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed 1M..10M if not exists
INSERT INTO `class_level` (`code`, `title`, `description`)
VALUES
 ('1M','Class 1M','Indian Music Foundations'),
 ('2M','Class 2M','Rhythm & Basic Ragas'),
 ('3M','Class 3M','Voice Culture & Alankars'),
 ('4M','Class 4M','Raga Development I'),
 ('5M','Class 5M','Raga Development II'),
 ('6M','Class 6M','Taal & Layakari'),
 ('7M','Class 7M','Bandish & Presentation'),
 ('8M','Class 8M','Advanced Ragas'),
 ('9M','Class 9M','Performance Training'),
 ('10M','Class 10M','Mastery & Stage Readiness')
ON DUPLICATE KEY UPDATE `title`=VALUES(`title`);

-- 3) Syllabus Items
CREATE TABLE IF NOT EXISTS `syllabus_item` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `class_level_id` INT NOT NULL,
  `unit_no` INT NULL,                  -- optional (unit/week)
  `topic` VARCHAR(200) NOT NULL,
  `details` TEXT NULL,
  `resource_link` VARCHAR(500) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_syllabus_class_level` (`class_level_id`),
  CONSTRAINT `fk_syllabus_class_level`
    FOREIGN KEY (`class_level_id`) REFERENCES `class_level`(`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4) Venues
CREATE TABLE IF NOT EXISTS `venue` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(120) NOT NULL,
  `address` VARCHAR(255) NULL,
  `notes` TEXT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5) Teachers
CREATE TABLE IF NOT EXISTS `teacher` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(255) NULL,
  `bio` TEXT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `default_venue_id` INT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_teacher_active` (`is_active`),
  CONSTRAINT `fk_teacher_default_venue`
    FOREIGN KEY (`default_venue_id`) REFERENCES `venue`(`id`)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6) Teacher availability slots (bookable)
CREATE TABLE IF NOT EXISTS `teacher_availability` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `teacher_id` INT NOT NULL,
  `start_at` DATETIME NOT NULL,
  `end_at` DATETIME NOT NULL,
  `venue_id` INT NULL,
  `is_booked` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_avail_teacher` (`teacher_id`),
  KEY `ix_avail_start` (`start_at`),
  UNIQUE KEY `uq_avail_unique` (`teacher_id`, `start_at`, `end_at`),
  CONSTRAINT `fk_avail_teacher`
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_avail_venue`
    FOREIGN KEY (`venue_id`) REFERENCES `venue`(`id`)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7) Bookings (log)
CREATE TABLE IF NOT EXISTS `booking` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `teacher_id` INT NOT NULL,
  `availability_id` INT NOT NULL,
  `student_name` VARCHAR(120) NOT NULL,
  `student_email` VARCHAR(255) NOT NULL,
  `student_phone` VARCHAR(60) NULL,
  `class_level_id` INT NULL,
  `venue_id` INT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'BOOKED', -- BOOKED/CANCELLED
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_booking_availability` (`availability_id`),
  KEY `ix_booking_teacher` (`teacher_id`),
  KEY `ix_booking_created` (`created_at`),
  CONSTRAINT `fk_booking_teacher`
    FOREIGN KEY (`teacher_id`) REFERENCES `teacher`(`id`)
    ON DELETE RESTRICT,
  CONSTRAINT `fk_booking_availability`
    FOREIGN KEY (`availability_id`) REFERENCES `teacher_availability`(`id`)
    ON DELETE RESTRICT,
  CONSTRAINT `fk_booking_class_level`
    FOREIGN KEY (`class_level_id`) REFERENCES `class_level`(`id`)
    ON DELETE SET NULL,
  CONSTRAINT `fk_booking_venue`
    FOREIGN KEY (`venue_id`) REFERENCES `venue`(`id`)
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
