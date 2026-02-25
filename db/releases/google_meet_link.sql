USE `deep3576$TheSpiritSchool_ProdDB`;

ALTER TABLE `booking`
  ADD COLUMN IF NOT EXISTS `google_meet_link` VARCHAR(500) NULL AFTER `status`;
