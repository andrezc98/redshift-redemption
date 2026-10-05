-- Fallback when the S3 Tables integration blocks for more than 1 hour: Iceberg in the lake
-- bucket behind a Glue external schema. External schema, not the auto-mounted Glue catalog,
-- because the auto-mount needs an IAM-identity connection and the runner connects as awsuser.
-- Iceberg has no CHAR type: char(n) columns are cast to varchar(n) (error of 2026-10-05).
-- start template schema
CREATE EXTERNAL SCHEMA IF NOT EXISTS ice FROM DATA CATALOG DATABASE 'rr_iceberg' IAM_ROLE default;
-- end template schema
-- start template b_date_dim
CREATE TABLE ice.date_dim USING ICEBERG LOCATION 's3://{bucket}/iceberg/date_dim/' AS SELECT d_date_sk, d_date_id::varchar(16) AS d_date_id, d_date, d_month_seq, d_week_seq, d_quarter_seq, d_year, d_dow, d_moy, d_dom, d_qoy, d_fy_year, d_fy_quarter_seq, d_fy_week_seq, d_day_name::varchar(9) AS d_day_name, d_quarter_name::varchar(6) AS d_quarter_name, d_holiday::varchar(1) AS d_holiday, d_weekend::varchar(1) AS d_weekend, d_following_holiday::varchar(1) AS d_following_holiday, d_first_dom, d_last_dom, d_same_day_ly, d_same_day_lq, d_current_day::varchar(1) AS d_current_day, d_current_week::varchar(1) AS d_current_week, d_current_month::varchar(1) AS d_current_month, d_current_quarter::varchar(1) AS d_current_quarter, d_current_year::varchar(1) AS d_current_year FROM public.date_dim;
-- end template b_date_dim
-- start template b_item
CREATE TABLE ice.item USING ICEBERG LOCATION 's3://{bucket}/iceberg/item/' AS SELECT i_item_sk, i_item_id::varchar(16) AS i_item_id, i_rec_start_date, i_rec_end_date, i_item_desc, i_current_price, i_wholesale_cost, i_brand_id, i_brand::varchar(50) AS i_brand, i_class_id, i_class::varchar(50) AS i_class, i_category_id, i_category::varchar(50) AS i_category, i_manufact_id, i_manufact::varchar(50) AS i_manufact, i_size::varchar(20) AS i_size, i_formulation::varchar(20) AS i_formulation, i_color::varchar(20) AS i_color, i_units::varchar(10) AS i_units, i_container::varchar(10) AS i_container, i_manager_id, i_product_name::varchar(50) AS i_product_name FROM public.item;
-- end template b_item
-- start template b_store
CREATE TABLE ice.store USING ICEBERG LOCATION 's3://{bucket}/iceberg/store/' AS SELECT s_store_sk, s_store_id::varchar(16) AS s_store_id, s_rec_start_date, s_rec_end_date, s_closed_date_sk, s_store_name, s_number_employees, s_floor_space, s_hours::varchar(20) AS s_hours, s_manager, s_market_id, s_geography_class, s_market_desc, s_market_manager, s_division_id, s_division_name, s_company_id, s_company_name, s_street_number, s_street_name, s_street_type::varchar(15) AS s_street_type, s_suite_number::varchar(10) AS s_suite_number, s_city, s_county, s_state::varchar(2) AS s_state, s_zip::varchar(10) AS s_zip, s_country, s_gmt_offset, s_tax_precentage FROM public.store;
-- end template b_store
-- start template b_customer
CREATE TABLE ice.customer USING ICEBERG LOCATION 's3://{bucket}/iceberg/customer/' AS SELECT c_customer_sk, c_customer_id::varchar(16) AS c_customer_id, c_current_cdemo_sk, c_current_hdemo_sk, c_current_addr_sk, c_first_shipto_date_sk, c_first_sales_date_sk, c_salutation::varchar(10) AS c_salutation, c_first_name::varchar(20) AS c_first_name, c_last_name::varchar(30) AS c_last_name, c_preferred_cust_flag::varchar(1) AS c_preferred_cust_flag, c_birth_day, c_birth_month, c_birth_year, c_birth_country, c_login::varchar(13) AS c_login, c_email_address::varchar(50) AS c_email_address, c_last_review_date_sk FROM public.customer;
-- end template b_customer
-- start template b_store_sales
CREATE TABLE ice.store_sales USING ICEBERG LOCATION 's3://{bucket}/iceberg/store_sales/' AS SELECT * FROM public.store_sales;
-- end template b_store_sales
