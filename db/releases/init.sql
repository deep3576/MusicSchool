/* =========================================================
   TheSpiritSchool.ca - Release 001 (Initial Schema)
   Database: deep3576$TheSpiritSchool_ProdDB
   Notes:
   - Admin user password is hashed by Flask CLI (recommended).
   - This script creates tables only.
   ========================================================= */

USE `deep3576$TheSpiritSchool_ProdDB`;

-- Ensure consistent charset for new tables
SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- 1) Migration tracking table
CREATE TABLE IF NOT EXISTS `schema_migrations` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `release` VARCHAR(50) NOT NULL,
  `description` VARCHAR(255) NOT NULL,
  `applied_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_schema_migrations_release` (`release`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2) Admin users table (used by Flask-Login)
-- NOTE: table name is `user` because your SQLAlchemy model defaults to that.
CREATE TABLE IF NOT EXISTS `user` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3) Contact form messages
CREATE TABLE IF NOT EXISTS `contact_message` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(120) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `phone` VARCHAR(60) NULL,
  `subject` VARCHAR(160) NOT NULL,
  `message` TEXT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_contact_message_email` (`email`),
  KEY `ix_contact_message_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4) Record this release as applied
INSERT INTO `schema_migrations` (`release`, `description`)
VALUES ('001', 'Initial schema: schema_migrations, user, contact_message')
ON DUPLICATE KEY UPDATE
  `description` = VALUES(`description`);
