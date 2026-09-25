-- start template skew
SELECT "table", tbl_rows, skew_rows, skew_sortkey1 FROM svv_table_info ORDER BY skew_rows DESC NULLS LAST;
-- end template skew
