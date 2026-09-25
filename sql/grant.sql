-- Serverless maps the Data API caller to an IAM:/IAMR: database user, which owns nothing
-- after the restore. Run on rr-ra3 BEFORE the snapshot (sandbox lab data, nothing private).
-- start template grant
GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
-- end template grant
