-- Reviewed and approved by Heloise 
BEGIN;

ALTER TABLE feature_making ADD COLUMN lvra INTEGER DEFAULT 0;
UPDATE feature_making SET lvra = NULL;

ALTER TABLE predict ADD COLUMN lvra INTEGER DEFAULT 0;
UPDATE predict SET lvra = NULL;

ALTER TABLE annotating ADD COLUMN lvra INTEGER DEFAULT 0;
UPDATE annotating SET lvra = NULL;

COMMIT;
