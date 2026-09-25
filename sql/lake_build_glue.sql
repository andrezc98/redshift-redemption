-- start template b_date_dim
CREATE TABLE awsdatacatalog.rr_iceberg.date_dim USING ICEBERG LOCATION 's3://{bucket}/iceberg/date_dim/' AS SELECT * FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE TABLE awsdatacatalog.rr_iceberg.item USING ICEBERG LOCATION 's3://{bucket}/iceberg/item/' AS SELECT * FROM public.item;
-- end template b_item
-- start template b_store
CREATE TABLE awsdatacatalog.rr_iceberg.store USING ICEBERG LOCATION 's3://{bucket}/iceberg/store/' AS SELECT * FROM public.store;
-- end template b_store
-- start template b_customer
CREATE TABLE awsdatacatalog.rr_iceberg.customer USING ICEBERG LOCATION 's3://{bucket}/iceberg/customer/' AS SELECT * FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE TABLE awsdatacatalog.rr_iceberg.store_sales USING ICEBERG LOCATION 's3://{bucket}/iceberg/store_sales/' AS SELECT * FROM public.store_sales;
-- end template b_store_sales
