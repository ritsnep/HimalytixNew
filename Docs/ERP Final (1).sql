CREATE TABLE [tenants] (
  [tenant_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_uuid] UUID UNIQUE NOT NULL DEFAULT (uuid_generate_v4()),
  [code] VARCHAR(50) UNIQUE NOT NULL,
  [name] VARCHAR(200) NOT NULL,
  [slug] VARCHAR(100) UNIQUE NOT NULL,
  [subscription_tier] VARCHAR(50) NOT NULL DEFAULT 'standard',
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [domain_name] VARCHAR(255) UNIQUE,
  [data_schema] VARCHAR(100) NOT NULL,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [deleted_at] TIMESTAMP
)
GO

CREATE TABLE [tenant_subscriptions] (
  [subscription_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_id] INTEGER NOT NULL,
  [plan_id] INTEGER NOT NULL,
  [start_date] DATE NOT NULL,
  [end_date] DATE NOT NULL,
  [auto_renew] BOOLEAN NOT NULL DEFAULT (true),
  [status] VARCHAR(50) NOT NULL DEFAULT 'active',
  [billing_cycle] VARCHAR(20) NOT NULL DEFAULT 'monthly',
  [price_per_period] DECIMAL(12,2) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [next_billing_date] DATE NOT NULL,
  [last_billing_date] DATE,
  [payment_method_id] INTEGER,
  [cancellation_date] TIMESTAMP,
  [cancellation_reason] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [subscription_plans] (
  [plan_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [code] VARCHAR(50) UNIQUE NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [base_price] DECIMAL(12,2) NOT NULL,
  [billing_cycle] VARCHAR(20) NOT NULL DEFAULT 'monthly',
  [max_users] INTEGER NOT NULL,
  [max_storage_gb] INTEGER NOT NULL,
  [features] JSONB NOT NULL DEFAULT '{}',
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [tenant_config] (
  [config_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_id] INTEGER NOT NULL,
  [config_key] VARCHAR(100) NOT NULL,
  [config_value] TEXT,
  [data_type] VARCHAR(20) NOT NULL DEFAULT 'string',
  [is_encrypted] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [organizations] (
  [organization_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_id] INTEGER NOT NULL,
  [parent_organization_id] INTEGER,
  [name] VARCHAR(200) NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [type] VARCHAR(50) NOT NULL,
  [legal_name] VARCHAR(200),
  [tax_id] VARCHAR(50),
  [registration_number] VARCHAR(50),
  [industry_code] VARCHAR(20),
  [fiscal_year_start_month] SMALLINT NOT NULL DEFAULT (1),
  [fiscal_year_start_day] SMALLINT NOT NULL DEFAULT (1),
  [base_currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [status] VARCHAR(20) NOT NULL DEFAULT 'active',
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [organization_addresses] (
  [address_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [address_type] VARCHAR(50) NOT NULL,
  [address_line1] VARCHAR(200) NOT NULL,
  [address_line2] VARCHAR(200),
  [city] VARCHAR(100) NOT NULL,
  [state_province] VARCHAR(100),
  [postal_code] VARCHAR(20),
  [country_code] CHAR (2) NOT NULL,
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [latitude] DECIMAL(10,7),
  [longitude] DECIMAL(10,7),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [organization_contacts] (
  [contact_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [contact_type] VARCHAR(50) NOT NULL,
  [name] VARCHAR(200) NOT NULL,
  [email] VARCHAR(255) NOT NULL,
  [phone] VARCHAR(50),
  [job_title] VARCHAR(100),
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [users] (
  [user_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_id] INTEGER NOT NULL,
  [user_uuid] UUID UNIQUE NOT NULL DEFAULT (uuid_generate_v4()),
  [organization_id] INTEGER,
  [username] VARCHAR(100) NOT NULL,
  [email] VARCHAR(255) NOT NULL,
  [display_name] VARCHAR(200),
  [status] VARCHAR(20) NOT NULL DEFAULT 'active',
  [auth_provider] VARCHAR(50) NOT NULL DEFAULT 'local',
  [auth_provider_id] VARCHAR(255),
  [last_login_at] TIMESTAMP,
  [password_changed_at] TIMESTAMP,
  [password_reset_token] VARCHAR(100),
  [password_reset_expires] TIMESTAMP,
  [failed_login_attempts] SMALLINT NOT NULL DEFAULT (0),
  [locked_until] TIMESTAMP,
  [email_verified_at] TIMESTAMP,
  [email_verification_token] VARCHAR(100),
  [mfa_enabled] BOOLEAN NOT NULL DEFAULT (false),
  [mfa_type] VARCHAR(20),
  [mfa_secret] VARCHAR(100),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [deleted_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [user_profiles] (
  [profile_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [user_id] INTEGER NOT NULL,
  [first_name] VARCHAR(100),
  [last_name] VARCHAR(100),
  [phone] VARCHAR(50),
  [avatar_url] VARCHAR(255),
  [date_format] VARCHAR(20) DEFAULT 'yyyy-MM-dd',
  [time_format] VARCHAR(20) DEFAULT 'HH:mm:ss',
  [timezone] VARCHAR(50) DEFAULT 'UTC',
  [language_code] VARCHAR(10) DEFAULT 'en',
  [country_code] CHAR (2),
  [address_line1] VARCHAR(200),
  [address_line2] VARCHAR(200),
  [city] VARCHAR(100),
  [state_province] VARCHAR(100),
  [postal_code] VARCHAR(20),
  [biographical_info] TEXT,
  [job_title] VARCHAR(100),
  [department] VARCHAR(100),
  [employee_id] VARCHAR(50),
  [hire_date] DATE,
  [preferences] JSONB DEFAULT '{}',
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [roles] (
  [role_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_id] INTEGER NOT NULL,
  [role_uuid] UUID UNIQUE NOT NULL DEFAULT (uuid_generate_v4()),
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [is_system_role] BOOLEAN NOT NULL DEFAULT (false),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [permissions] (
  [permission_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [permission_uuid] UUID UNIQUE NOT NULL DEFAULT (uuid_generate_v4()),
  [module] VARCHAR(50) NOT NULL,
  [code] VARCHAR(100) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [category] VARCHAR(50),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [role_permissions] (
  [role_permission_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [role_id] INTEGER NOT NULL,
  [permission_id] INTEGER NOT NULL,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [user_roles] (
  [user_role_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [user_id] INTEGER NOT NULL,
  [role_id] INTEGER NOT NULL,
  [organization_id] INTEGER,
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [user_permissions] (
  [user_permission_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [user_id] INTEGER NOT NULL,
  [permission_id] INTEGER NOT NULL,
  [is_granted] BOOLEAN NOT NULL DEFAULT (true),
  [organization_id] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [access_logs] (
  [log_id] BIGSERIAL PRIMARY KEY IDENTITY(1, 1),
  [tenant_id] INTEGER NOT NULL,
  [user_id] INTEGER,
  [ip_address] VARCHAR(45) NOT NULL,
  [user_agent] TEXT,
  [event_type] VARCHAR(50) NOT NULL,
  [event_status] VARCHAR(20) NOT NULL,
  [event_data] JSONB,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW())
)
GO

CREATE TABLE [fiscal_years] (
  [fiscal_year_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(10) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [start_date] DATE NOT NULL,
  [end_date] DATE NOT NULL,
  [status] VARCHAR(20) NOT NULL DEFAULT 'open',
  [is_current] BOOLEAN NOT NULL DEFAULT (false),
  [closed_at] TIMESTAMP,
  [closed_by] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [accounting_periods] (
  [period_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [fiscal_year_id] INTEGER NOT NULL,
  [period_number] SMALLINT NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [start_date] DATE NOT NULL,
  [end_date] DATE NOT NULL,
  [status] VARCHAR(20) NOT NULL DEFAULT 'open',
  [is_adjustment_period] BOOLEAN NOT NULL DEFAULT (false),
  [closed_at] TIMESTAMP,
  [closed_by] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [account_types] (
  [account_type_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [code] VARCHAR(20) UNIQUE NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [nature] VARCHAR(10) NOT NULL,
  [classification] VARCHAR(50) NOT NULL,
  [balance_sheet_category] VARCHAR(50),
  [income_statement_category] VARCHAR(50),
  [cash_flow_category] VARCHAR(50),
  [system_type] BOOLEAN NOT NULL DEFAULT (true),
  [display_order] INTEGER NOT NULL,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [chart_of_accounts] (
  [account_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [parent_account_id] INTEGER,
  [account_type_id] INTEGER NOT NULL,
  [account_code] VARCHAR(50) NOT NULL,
  [account_name] VARCHAR(200) NOT NULL,
  [description] TEXT,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [is_bank_account] BOOLEAN NOT NULL DEFAULT (false),
  [is_control_account] BOOLEAN NOT NULL DEFAULT (false),
  [control_account_type] VARCHAR(50),
  [require_cost_center] BOOLEAN NOT NULL DEFAULT (false),
  [require_project] BOOLEAN NOT NULL DEFAULT (false),
  [require_department] BOOLEAN NOT NULL DEFAULT (false),
  [default_tax_code] VARCHAR(50),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [opening_balance] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [current_balance] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [reconciled_balance] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [last_reconciled_date] TIMESTAMP,
  [allow_manual_journal] BOOLEAN NOT NULL DEFAULT (true),
  [account_level] SMALLINT NOT NULL DEFAULT (1),
  [tree_path] VARCHAR(255),
  [display_order] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [currency_exchange_rates] (
  [rate_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [from_currency] CHAR (3) NOT NULL,
  [to_currency] CHAR (3) NOT NULL,
  [rate_date] DATE NOT NULL,
  [exchange_rate] DECIMAL(19,6) NOT NULL,
  [is_average_rate] BOOLEAN NOT NULL DEFAULT (false),
  [source] VARCHAR(50) NOT NULL DEFAULT 'manual',
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [journal_types] (
  [journal_type_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(20) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [auto_numbering_prefix] VARCHAR(10),
  [auto_numbering_suffix] VARCHAR(10),
  [auto_numbering_next] INTEGER NOT NULL DEFAULT (1),
  [is_system_type] BOOLEAN NOT NULL DEFAULT (false),
  [requires_approval] BOOLEAN NOT NULL DEFAULT (false),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [journals] (
  [journal_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [journal_number] VARCHAR(50) NOT NULL,
  [journal_type_id] INTEGER NOT NULL,
  [period_id] INTEGER NOT NULL,
  [journal_date] DATE NOT NULL,
  [reference] VARCHAR(100),
  [description] TEXT,
  [source_module] VARCHAR(50),
  [source_reference] VARCHAR(100),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [total_debit] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_credit] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [status] VARCHAR(20) NOT NULL DEFAULT 'draft',
  [is_recurring] BOOLEAN NOT NULL DEFAULT (false),
  [recurring_template_id] INTEGER,
  [is_reversal] BOOLEAN NOT NULL DEFAULT (false),
  [reversed_journal_id] INTEGER,
  [reversal_reason] TEXT,
  [posted_at] TIMESTAMP,
  [posted_by] INTEGER,
  [approved_at] TIMESTAMP,
  [approved_by] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [journal_lines] (
  [journal_line_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [journal_id] INTEGER NOT NULL,
  [line_number] INTEGER NOT NULL,
  [account_id] INTEGER NOT NULL,
  [description] TEXT,
  [debit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [credit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [functional_debit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [functional_credit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [department_id] INTEGER,
  [project_id] INTEGER,
  [cost_center_id] INTEGER,
  [tax_code_id] INTEGER,
  [tax_rate] DECIMAL(8,4),
  [tax_amount] DECIMAL(19,4),
  [memo] TEXT,
  [reconciled] BOOLEAN NOT NULL DEFAULT (false),
  [reconciled_at] TIMESTAMP,
  [reconciled_by] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [general_ledger] (
  [gl_entry_id] BIGSERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [account_id] INTEGER NOT NULL,
  [journal_id] INTEGER NOT NULL,
  [journal_line_id] INTEGER NOT NULL,
  [period_id] INTEGER NOT NULL,
  [transaction_date] DATE NOT NULL,
  [debit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [credit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [balance_after] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [functional_debit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [functional_credit_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [department_id] INTEGER,
  [project_id] INTEGER,
  [cost_center_id] INTEGER,
  [description] TEXT,
  [source_module] VARCHAR(50),
  [source_reference] VARCHAR(100),
  [is_adjustment] BOOLEAN NOT NULL DEFAULT (false),
  [is_closing_entry] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW())
)
GO

CREATE TABLE [tax_authorities] (
  [authority_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [country_code] CHAR (2) NOT NULL,
  [identifier] VARCHAR(100),
  [contact_info] TEXT,
  [api_endpoint] VARCHAR(255),
  [api_key] VARCHAR(255),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [tax_types] (
  [tax_type_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(20) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [authority_id] INTEGER,
  [description] TEXT,
  [filing_frequency] VARCHAR(50),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [is_system_type] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [tax_codes] (
  [tax_code_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [tax_type_id] INTEGER NOT NULL,
  [code] VARCHAR(20) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [rate] DECIMAL(8,4) NOT NULL DEFAULT (0),
  [is_recoverable] BOOLEAN NOT NULL DEFAULT (true),
  [is_compound] BOOLEAN NOT NULL DEFAULT (false),
  [effective_from] DATE NOT NULL,
  [effective_to] DATE,
  [sales_account_id] INTEGER,
  [purchase_account_id] INTEGER,
  [report_line_code] VARCHAR(50),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [customers] (
  [customer_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [customer_code] VARCHAR(50) NOT NULL,
  [customer_name] VARCHAR(200) NOT NULL,
  [legal_name] VARCHAR(200),
  [customer_type] VARCHAR(50) NOT NULL DEFAULT 'company',
  [tax_id] VARCHAR(50),
  [industry] VARCHAR(50),
  [website] VARCHAR(255),
  [credit_limit] DECIMAL(19,4),
  [payment_terms] VARCHAR(50),
  [payment_method] VARCHAR(50),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [gl_account_id] INTEGER,
  [status] VARCHAR(20) NOT NULL DEFAULT 'active',
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [customer_contacts] (
  [contact_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [customer_id] INTEGER NOT NULL,
  [first_name] VARCHAR(100) NOT NULL,
  [last_name] VARCHAR(100) NOT NULL,
  [email] VARCHAR(255),
  [phone] VARCHAR(50),
  [mobile] VARCHAR(50),
  [job_title] VARCHAR(100),
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [is_billing] BOOLEAN NOT NULL DEFAULT (false),
  [is_shipping] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [customer_addresses] (
  [address_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [customer_id] INTEGER NOT NULL,
  [address_type] VARCHAR(50) NOT NULL,
  [address_line1] VARCHAR(200) NOT NULL,
  [address_line2] VARCHAR(200),
  [city] VARCHAR(100) NOT NULL,
  [state_province] VARCHAR(100),
  [postal_code] VARCHAR(20),
  [country_code] CHAR (2) NOT NULL,
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [latitude] DECIMAL(10,7),
  [longitude] DECIMAL(10,7),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [sales_categories] (
  [category_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [parent_category_id] INTEGER,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [display_order] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [products] (
  [product_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [product_code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(200) NOT NULL,
  [description] TEXT,
  [category_id] INTEGER,
  [unit_of_measure] VARCHAR(50) NOT NULL DEFAULT 'each',
  [sale_price] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [cost_price] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [tax_code_id] INTEGER,
  [income_account_id] INTEGER,
  [expense_account_id] INTEGER,
  [inventory_account_id] INTEGER,
  [is_inventory_item] BOOLEAN NOT NULL DEFAULT (false),
  [is_sold] BOOLEAN NOT NULL DEFAULT (true),
  [is_purchased] BOOLEAN NOT NULL DEFAULT (true),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [min_order_quantity] DECIMAL(15,4) DEFAULT (1),
  [reorder_level] DECIMAL(15,4),
  [preferred_vendor_id] INTEGER,
  [weight] DECIMAL(10,2),
  [weight_unit] VARCHAR(10),
  [dimensions] VARCHAR(50),
  [barcode] VARCHAR(100),
  [sku] VARCHAR(100),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [price_lists] (
  [price_list_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [effective_from] DATE NOT NULL,
  [effective_to] DATE,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [price_list_items] (
  [price_item_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [price_list_id] INTEGER NOT NULL,
  [product_id] INTEGER NOT NULL,
  [price] DECIMAL(19,4) NOT NULL,
  [min_quantity] DECIMAL(15,4) DEFAULT (1),
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [customer_price_lists] (
  [customer_price_list_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [customer_id] INTEGER NOT NULL,
  [price_list_id] INTEGER NOT NULL,
  [is_default] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [sales_quotes] (
  [quote_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [quote_number] VARCHAR(50) NOT NULL,
  [customer_id] INTEGER NOT NULL,
  [customer_contact_id] INTEGER,
  [quote_date] DATE NOT NULL,
  [expiry_date] DATE NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [price_list_id] INTEGER,
  [payment_terms] VARCHAR(50),
  [delivery_method] VARCHAR(50),
  [shipping_address_id] INTEGER,
  [billing_address_id] INTEGER,
  [status] VARCHAR(20) NOT NULL DEFAULT 'draft',
  [reference] VARCHAR(100),
  [total_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_discount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [grand_total] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [notes] TEXT,
  [terms_and_conditions] TEXT,
  [converted_to_order_id] INTEGER,
  [converted_date] TIMESTAMP,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [sales_quote_lines] (
  [quote_line_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [quote_id] INTEGER NOT NULL,
  [line_number] INTEGER NOT NULL,
  [product_id] INTEGER NOT NULL,
  [description] TEXT,
  [quantity] DECIMAL(15,4) NOT NULL,
  [unit_price] DECIMAL(19,4) NOT NULL,
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [discount_amount] DECIMAL(19,4) DEFAULT (0),
  [tax_code_id] INTEGER,
  [tax_rate] DECIMAL(8,4),
  [tax_amount] DECIMAL(19,4) DEFAULT (0),
  [line_amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [sales_orders] (
  [order_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [order_number] VARCHAR(50) NOT NULL,
  [customer_id] INTEGER NOT NULL,
  [customer_contact_id] INTEGER,
  [customer_po_number] VARCHAR(100),
  [quote_id] INTEGER,
  [order_date] DATE NOT NULL,
  [expected_delivery_date] DATE,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [price_list_id] INTEGER,
  [payment_terms] VARCHAR(50),
  [delivery_method] VARCHAR(50),
  [shipping_address_id] INTEGER,
  [billing_address_id] INTEGER,
  [status] VARCHAR(20) NOT NULL DEFAULT 'open',
  [fulfillment_status] VARCHAR(20) NOT NULL DEFAULT 'pending',
  [invoice_status] VARCHAR(20) NOT NULL DEFAULT 'pending',
  [reference] VARCHAR(100),
  [total_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_discount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_charge] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [grand_total] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [notes] TEXT,
  [terms_and_conditions] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [sales_order_lines] (
  [order_line_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [order_id] INTEGER NOT NULL,
  [line_number] INTEGER NOT NULL,
  [product_id] INTEGER NOT NULL,
  [description] TEXT,
  [quantity] DECIMAL(15,4) NOT NULL,
  [quantity_shipped] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [quantity_invoiced] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [unit_price] DECIMAL(19,4) NOT NULL,
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [discount_amount] DECIMAL(19,4) DEFAULT (0),
  [tax_code_id] INTEGER,
  [tax_rate] DECIMAL(8,4),
  [tax_amount] DECIMAL(19,4) DEFAULT (0),
  [line_amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [expected_ship_date] DATE,
  [quote_line_id] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [invoices] (
  [invoice_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [invoice_number] VARCHAR(50) NOT NULL,
  [customer_id] INTEGER NOT NULL,
  [order_id] INTEGER,
  [invoice_date] DATE NOT NULL,
  [due_date] DATE NOT NULL,
  [payment_terms_id] INTEGER,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [billing_address_id] INTEGER,
  [shipping_address_id] INTEGER,
  [status] VARCHAR(20) NOT NULL DEFAULT 'draft',
  [reference] VARCHAR(100),
  [customer_po_number] VARCHAR(100),
  [journal_id] INTEGER,
  [total_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_discount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_charge] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [grand_total] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [amount_paid] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [amount_due] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [notes] TEXT,
  [terms_and_conditions] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [invoice_lines] (
  [invoice_line_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [invoice_id] INTEGER NOT NULL,
  [line_number] INTEGER NOT NULL,
  [product_id] INTEGER NOT NULL,
  [description] TEXT,
  [quantity] DECIMAL(15,4) NOT NULL,
  [unit_price] DECIMAL(19,4) NOT NULL,
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [discount_amount] DECIMAL(19,4) DEFAULT (0),
  [tax_code_id] INTEGER,
  [tax_rate] DECIMAL(8,4),
  [tax_amount] DECIMAL(19,4) DEFAULT (0),
  [line_amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [order_line_id] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [vendors] (
  [vendor_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [vendor_code] VARCHAR(50) NOT NULL,
  [vendor_name] VARCHAR(200) NOT NULL,
  [legal_name] VARCHAR(200),
  [vendor_type] VARCHAR(50) NOT NULL DEFAULT 'company',
  [tax_id] VARCHAR(50),
  [industry] VARCHAR(50),
  [website] VARCHAR(255),
  [credit_terms] VARCHAR(50),
  [payment_terms] VARCHAR(50),
  [payment_method] VARCHAR(50),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [gl_account_id] INTEGER,
  [status] VARCHAR(20) NOT NULL DEFAULT 'active',
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [vendor_contacts] (
  [contact_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [vendor_id] INTEGER NOT NULL,
  [first_name] VARCHAR(100) NOT NULL,
  [last_name] VARCHAR(100) NOT NULL,
  [email] VARCHAR(255),
  [phone] VARCHAR(50),
  [mobile] VARCHAR(50),
  [job_title] VARCHAR(100),
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [is_billing] BOOLEAN NOT NULL DEFAULT (false),
  [is_orders] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [vendor_addresses] (
  [address_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [vendor_id] INTEGER NOT NULL,
  [address_type] VARCHAR(50) NOT NULL,
  [address_line1] VARCHAR(200) NOT NULL,
  [address_line2] VARCHAR(200),
  [city] VARCHAR(100) NOT NULL,
  [state_province] VARCHAR(100),
  [postal_code] VARCHAR(20),
  [country_code] CHAR (2) NOT NULL,
  [is_primary] BOOLEAN NOT NULL DEFAULT (false),
  [latitude] DECIMAL(10,7),
  [longitude] DECIMAL(10,7),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [purchase_orders] (
  [po_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [po_number] VARCHAR(50) NOT NULL,
  [vendor_id] INTEGER NOT NULL,
  [vendor_contact_id] INTEGER,
  [po_date] DATE NOT NULL,
  [expected_delivery_date] DATE,
  [delivery_address_id] INTEGER,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [payment_terms] VARCHAR(50),
  [status] VARCHAR(20) NOT NULL DEFAULT 'draft',
  [receipt_status] VARCHAR(20) NOT NULL DEFAULT 'pending',
  [bill_status] VARCHAR(20) NOT NULL DEFAULT 'pending',
  [reference] VARCHAR(100),
  [total_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_discount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_charge] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [grand_total] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [notes] TEXT,
  [terms_and_conditions] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [purchase_order_lines] (
  [po_line_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [po_id] INTEGER NOT NULL,
  [line_number] INTEGER NOT NULL,
  [product_id] INTEGER NOT NULL,
  [description] TEXT,
  [quantity] DECIMAL(15,4) NOT NULL,
  [quantity_received] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [quantity_billed] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [unit_price] DECIMAL(19,4) NOT NULL,
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [discount_amount] DECIMAL(19,4) DEFAULT (0),
  [tax_code_id] INTEGER,
  [tax_rate] DECIMAL(8,4),
  [tax_amount] DECIMAL(19,4) DEFAULT (0),
  [line_amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [expected_delivery_date] DATE,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [vendor_bills] (
  [bill_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [bill_number] VARCHAR(50) NOT NULL,
  [vendor_id] INTEGER NOT NULL,
  [po_id] INTEGER,
  [vendor_bill_number] VARCHAR(100),
  [bill_date] DATE NOT NULL,
  [due_date] DATE NOT NULL,
  [payment_terms_id] INTEGER,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [status] VARCHAR(20) NOT NULL DEFAULT 'open',
  [reference] VARCHAR(100),
  [journal_id] INTEGER,
  [total_amount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_discount] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_charge] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [shipping_tax] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [grand_total] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [amount_paid] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [amount_due] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [vendor_bill_lines] (
  [bill_line_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [bill_id] INTEGER NOT NULL,
  [line_number] INTEGER NOT NULL,
  [product_id] INTEGER,
  [account_id] INTEGER,
  [description] TEXT,
  [quantity] DECIMAL(15,4) NOT NULL,
  [unit_price] DECIMAL(19,4) NOT NULL,
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [discount_amount] DECIMAL(19,4) DEFAULT (0),
  [tax_code_id] INTEGER,
  [tax_rate] DECIMAL(8,4),
  [tax_amount] DECIMAL(19,4) DEFAULT (0),
  [line_amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [po_line_id] INTEGER,
  [department_id] INTEGER,
  [project_id] INTEGER,
  [cost_center_id] INTEGER,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [warehouses] (
  [warehouse_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [address_line1] VARCHAR(200) NOT NULL,
  [address_line2] VARCHAR(200),
  [city] VARCHAR(100) NOT NULL,
  [state_province] VARCHAR(100),
  [postal_code] VARCHAR(20),
  [country_code] CHAR (2) NOT NULL,
  [contact_name] VARCHAR(200),
  [contact_email] VARCHAR(255),
  [contact_phone] VARCHAR(50),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [inventory_locations] (
  [location_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [warehouse_id] INTEGER NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [location_type] VARCHAR(50) NOT NULL DEFAULT 'storage',
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [inventory_items] (
  [inventory_item_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [product_id] INTEGER NOT NULL,
  [warehouse_id] INTEGER NOT NULL,
  [location_id] INTEGER,
  [batch_number] VARCHAR(100),
  [serial_number] VARCHAR(100),
  [expiry_date] DATE,
  [manufacture_date] DATE,
  [quantity_on_hand] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [quantity_allocated] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [quantity_available] DECIMAL(15,4) NOT NULL DEFAULT (0),
  [unit_cost] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [total_cost] DECIMAL(19,4) NOT NULL DEFAULT (0),
  [reorder_level] DECIMAL(15,4),
  [reorder_quantity] DECIMAL(15,4),
  [last_count_date] TIMESTAMP,
  [last_received_date] TIMESTAMP,
  [last_issued_date] TIMESTAMP,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [inventory_transactions] (
  [transaction_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [transaction_type] VARCHAR(50) NOT NULL,
  [transaction_date] TIMESTAMP NOT NULL,
  [reference_type] VARCHAR(50),
  [reference_id] INTEGER,
  [product_id] INTEGER NOT NULL,
  [from_warehouse_id] INTEGER,
  [from_location_id] INTEGER,
  [to_warehouse_id] INTEGER,
  [to_location_id] INTEGER,
  [batch_number] VARCHAR(100),
  [serial_number] VARCHAR(100),
  [quantity] DECIMAL(15,4) NOT NULL,
  [unit_cost] DECIMAL(19,4) NOT NULL,
  [total_cost] DECIMAL(19,4) NOT NULL,
  [journal_id] INTEGER,
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [departments] (
  [department_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [parent_department_id] INTEGER,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [manager_user_id] INTEGER,
  [cost_center_id] INTEGER,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [cost_centers] (
  [cost_center_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [parent_cost_center_id] INTEGER,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [manager_user_id] INTEGER,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [projects] (
  [project_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(200) NOT NULL,
  [description] TEXT,
  [customer_id] INTEGER,
  [project_manager_id] INTEGER,
  [start_date] DATE,
  [end_date] DATE,
  [estimated_hours] DECIMAL(10,2),
  [actual_hours] DECIMAL(10,2),
  [budget_amount] DECIMAL(19,4),
  [actual_amount] DECIMAL(19,4),
  [status] VARCHAR(50) NOT NULL DEFAULT 'active',
  [completion_percentage] DECIMAL(5,2) DEFAULT (0),
  [priority] VARCHAR(20) DEFAULT 'medium',
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [payment_methods] (
  [payment_method_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [type] VARCHAR(50) NOT NULL,
  [gl_account_id] INTEGER,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [is_default] BOOLEAN NOT NULL DEFAULT (false),
  [processing_fee_percentage] DECIMAL(5,2) DEFAULT (0),
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [payment_terms] (
  [payment_terms_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [code] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [days_due] INTEGER NOT NULL DEFAULT (0),
  [discount_percentage] DECIMAL(5,2) DEFAULT (0),
  [discount_days] INTEGER DEFAULT (0),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [is_default] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [customer_payments] (
  [payment_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [payment_number] VARCHAR(50) NOT NULL,
  [customer_id] INTEGER NOT NULL,
  [payment_date] DATE NOT NULL,
  [payment_method_id] INTEGER,
  [payment_reference] VARCHAR(100),
  [amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [status] VARCHAR(20) NOT NULL DEFAULT 'received',
  [journal_id] INTEGER,
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [payment_allocations] (
  [allocation_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [payment_id] INTEGER NOT NULL,
  [invoice_id] INTEGER NOT NULL,
  [amount] DECIMAL(19,4) NOT NULL,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [vendor_payments] (
  [payment_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [payment_number] VARCHAR(50) NOT NULL,
  [vendor_id] INTEGER NOT NULL,
  [payment_date] DATE NOT NULL,
  [payment_method_id] INTEGER,
  [payment_reference] VARCHAR(100),
  [amount] DECIMAL(19,4) NOT NULL,
  [currency_code] CHAR (3) NOT NULL DEFAULT 'USD',
  [exchange_rate] DECIMAL(19,6) NOT NULL DEFAULT (1),
  [status] VARCHAR(20) NOT NULL DEFAULT 'sent',
  [journal_id] INTEGER,
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [vendor_payment_allocations] (
  [allocation_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [payment_id] INTEGER NOT NULL,
  [bill_id] INTEGER NOT NULL,
  [amount] DECIMAL(19,4) NOT NULL,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [created_by] INTEGER
)
GO

CREATE TABLE [activity_logs] (
  [log_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [user_id] INTEGER,
  [activity_type] VARCHAR(100) NOT NULL,
  [activity_date] TIMESTAMP NOT NULL,
  [entity_type] VARCHAR(100) NOT NULL,
  [entity_id] INTEGER NOT NULL,
  [old_values] JSONB,
  [new_values] JSONB,
  [ip_address] VARCHAR(45),
  [user_agent] TEXT,
  [notes] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW())
)
GO

CREATE TABLE [report_definitions] (
  [report_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [report_code] VARCHAR(50) NOT NULL,
  [report_name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [report_type] VARCHAR(50) NOT NULL,
  [report_query] TEXT,
  [report_parameters] JSONB,
  [formatting_options] JSONB,
  [is_system] BOOLEAN NOT NULL DEFAULT (false),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [scheduled_reports] (
  [schedule_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [report_id] INTEGER NOT NULL,
  [schedule_name] VARCHAR(100) NOT NULL,
  [frequency] VARCHAR(50) NOT NULL,
  [day_of_week] INTEGER,
  [day_of_month] INTEGER,
  [start_date] DATE NOT NULL,
  [end_date] DATE,
  [last_run_at] TIMESTAMP,
  [next_run_at] TIMESTAMP,
  [report_parameters] JSONB,
  [recipients] JSONB,
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [system_settings] (
  [setting_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [setting_key] VARCHAR(100) NOT NULL,
  [setting_value] TEXT,
  [setting_group] VARCHAR(50) NOT NULL DEFAULT 'general',
  [is_system] BOOLEAN NOT NULL DEFAULT (false),
  [is_encrypted] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [updated_by] INTEGER
)
GO

CREATE TABLE [organization_settings] (
  [setting_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [setting_key] VARCHAR(100) NOT NULL,
  [setting_value] TEXT,
  [setting_group] VARCHAR(50) NOT NULL DEFAULT 'general',
  [is_encrypted] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [updated_by] INTEGER
)
GO

CREATE TABLE [notification_templates] (
  [template_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER,
  [code] VARCHAR(100) NOT NULL,
  [name] VARCHAR(200) NOT NULL,
  [description] TEXT,
  [subject] TEXT,
  [content] TEXT,
  [content_html] TEXT,
  [notification_type] VARCHAR(50) NOT NULL,
  [event_trigger] VARCHAR(100) NOT NULL,
  [placeholders] JSONB,
  [is_system] BOOLEAN NOT NULL DEFAULT (false),
  [is_active] BOOLEAN NOT NULL DEFAULT (true),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [user_notifications] (
  [notification_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [user_id] INTEGER NOT NULL,
  [notification_type] VARCHAR(50) NOT NULL,
  [template_id] INTEGER,
  [subject] TEXT,
  [content] TEXT,
  [content_html] TEXT,
  [related_entity_type] VARCHAR(100),
  [related_entity_id] INTEGER,
  [status] VARCHAR(20) NOT NULL DEFAULT 'pending',
  [is_read] BOOLEAN NOT NULL DEFAULT (false),
  [read_at] TIMESTAMP,
  [sent_at] TIMESTAMP,
  [error_message] TEXT,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP
)
GO

CREATE TABLE [document_categories] (
  [category_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [parent_category_id] INTEGER,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [is_system] BOOLEAN NOT NULL DEFAULT (false),
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [documents] (
  [document_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INTEGER NOT NULL,
  [category_id] INTEGER,
  [document_type] VARCHAR(50) NOT NULL,
  [related_entity_type] VARCHAR(100),
  [related_entity_id] INTEGER,
  [title] VARCHAR(200) NOT NULL,
  [description] TEXT,
  [file_name] VARCHAR(255) NOT NULL,
  [file_path] VARCHAR(1000) NOT NULL,
  [file_size] BIGINT NOT NULL,
  [file_type] VARCHAR(100) NOT NULL,
  [file_hash] VARCHAR(64),
  [version] INTEGER NOT NULL DEFAULT (1),
  [status] VARCHAR(20) NOT NULL DEFAULT 'active',
  [tags] JSONB,
  [metadata] JSONB,
  [access_permissions] JSONB,
  [created_at] TIMESTAMP NOT NULL DEFAULT (NOW()),
  [updated_at] TIMESTAMP,
  [created_by] INTEGER,
  [updated_by] INTEGER
)
GO

CREATE TABLE [udf_entity_types] (
  [entity_type_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [entity_name] VARCHAR(100) NOT NULL,
  [table_name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [is_active] BIT NOT NULL DEFAULT (1),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_groups] (
  [field_group_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [entity_type_id] INT NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [display_order] INT NOT NULL DEFAULT (1),
  [is_active] BIT NOT NULL DEFAULT (1),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_definitions] (
  [field_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [entity_type_id] INT NOT NULL,
  [field_group_id] INT,
  [field_name] VARCHAR(100) NOT NULL,
  [display_name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [field_type] VARCHAR(50) NOT NULL,
  [is_required] BIT NOT NULL DEFAULT (0),
  [is_unique] BIT NOT NULL DEFAULT (0),
  [is_indexed] BIT NOT NULL DEFAULT (0),
  [is_searchable] BIT NOT NULL DEFAULT (0),
  [min_length] INT,
  [max_length] INT,
  [default_value] TEXT,
  [regex_validation] TEXT,
  [error_message] TEXT,
  [placeholder] TEXT,
  [help_text] TEXT,
  [display_order] INT NOT NULL DEFAULT (1),
  [is_active] BIT NOT NULL DEFAULT (1),
  [is_system] BIT NOT NULL DEFAULT (0),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_options] (
  [option_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [field_id] INT NOT NULL,
  [option_value] VARCHAR(100) NOT NULL,
  [option_label] VARCHAR(100) NOT NULL,
  [display_order] INT NOT NULL DEFAULT (1),
  [is_default] BIT NOT NULL DEFAULT (0),
  [is_active] BIT NOT NULL DEFAULT (1),
  [color_code] VARCHAR(20),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_references] (
  [reference_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [field_id] INT NOT NULL,
  [reference_entity_type_id] INT NOT NULL,
  [display_field] VARCHAR(100) NOT NULL,
  [value_field] VARCHAR(100) NOT NULL DEFAULT 'id',
  [filter_criteria] TEXT,
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_values] (
  [value_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [field_id] INT NOT NULL,
  [entity_id] INT NOT NULL,
  [text_value] TEXT,
  [number_value] DECIMAL(30,10),
  [date_value] DATE,
  [datetime_value] DATETIMEOFFSET,
  [boolean_value] BIT,
  [reference_value] INT,
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_multi_select_values] (
  [multi_select_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [value_id] INT NOT NULL,
  [option_id] INT NOT NULL,
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [created_by] INT
)
GO

CREATE TABLE [udf_field_visibility_rules] (
  [rule_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [field_id] INT NOT NULL,
  [condition_field_id] INT NOT NULL,
  [operator] VARCHAR(50) NOT NULL,
  [condition_value] TEXT NOT NULL,
  [is_active] BIT NOT NULL DEFAULT (1),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_layouts] (
  [layout_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [entity_type_id] INT NOT NULL,
  [layout_type] VARCHAR(50) NOT NULL,
  [name] VARCHAR(100) NOT NULL,
  [description] TEXT,
  [is_default] BIT NOT NULL DEFAULT (0),
  [is_active] BIT NOT NULL DEFAULT (1),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_layout_items] (
  [layout_item_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [layout_id] INT NOT NULL,
  [field_id] INT NOT NULL,
  [display_order] INT NOT NULL DEFAULT (1),
  [column_span] INT NOT NULL DEFAULT (1),
  [row_span] INT NOT NULL DEFAULT (1),
  [is_visible] BIT NOT NULL DEFAULT (1),
  [is_readonly] BIT NOT NULL DEFAULT (0),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_dependencies] (
  [dependency_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [field_id] INT NOT NULL,
  [dependent_field_id] INT NOT NULL,
  [condition_type] VARCHAR(50) NOT NULL,
  [condition_operator] VARCHAR(50) NOT NULL,
  [condition_value] TEXT,
  [is_active] BIT NOT NULL DEFAULT (1),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_calculated_fields] (
  [calculated_field_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [field_id] INT NOT NULL,
  [formula] TEXT NOT NULL,
  [input_fields] TEXT NOT NULL,
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE TABLE [udf_field_history] (
  [history_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [field_id] INT NOT NULL,
  [entity_id] INT NOT NULL,
  [old_value] TEXT,
  [new_value] TEXT,
  [changed_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [changed_by] INT
)
GO

CREATE TABLE [udf_field_permissions] (
  [permission_id] SERIAL PRIMARY KEY IDENTITY(1, 1),
  [organization_id] INT NOT NULL,
  [field_id] INT NOT NULL,
  [role_id] INT NOT NULL,
  [can_view] BIT NOT NULL DEFAULT (1),
  [can_edit] BIT NOT NULL DEFAULT (0),
  [created_at] DATETIMEOFFSET NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
  [updated_at] DATETIMEOFFSET,
  [created_by] INT,
  [updated_by] INT
)
GO

CREATE UNIQUE INDEX [tenant_subscriptions_index_0] ON [tenant_subscriptions] ("tenant_id", "plan_id")
GO

CREATE UNIQUE INDEX [tenant_config_index_1] ON [tenant_config] ("tenant_id", "config_key")
GO

CREATE UNIQUE INDEX [organizations_index_2] ON [organizations] ("tenant_id", "code")
GO

CREATE UNIQUE INDEX [users_index_3] ON [users] ("tenant_id", "username")
GO

CREATE UNIQUE INDEX [users_index_4] ON [users] ("tenant_id", "email")
GO

CREATE UNIQUE INDEX [user_profiles_index_5] ON [user_profiles] ("user_id")
GO

CREATE UNIQUE INDEX [roles_index_6] ON [roles] ("tenant_id", "code")
GO

CREATE UNIQUE INDEX [permissions_index_7] ON [permissions] ("module", "code")
GO

CREATE UNIQUE INDEX [role_permissions_index_8] ON [role_permissions] ("role_id", "permission_id")
GO

CREATE UNIQUE INDEX [user_roles_index_9] ON [user_roles] ("user_id", "role_id", "organization_id")
GO

CREATE UNIQUE INDEX [user_permissions_index_10] ON [user_permissions] ("user_id", "permission_id", "organization_id")
GO

CREATE INDEX [idx_access_logs_tenant_id] ON [access_logs] ("tenant_id")
GO

CREATE INDEX [idx_access_logs_user_id] ON [access_logs] ("user_id")
GO

CREATE INDEX [idx_access_logs_event_type] ON [access_logs] ("event_type")
GO

CREATE INDEX [idx_access_logs_created_at] ON [access_logs] ("created_at")
GO

CREATE UNIQUE INDEX [fiscal_years_index_15] ON [fiscal_years] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [accounting_periods_index_16] ON [accounting_periods] ("fiscal_year_id", "period_number")
GO

CREATE UNIQUE INDEX [chart_of_accounts_index_17] ON [chart_of_accounts] ("organization_id", "account_code")
GO

CREATE INDEX [idx_coa_organization_id] ON [chart_of_accounts] ("organization_id")
GO

CREATE INDEX [idx_coa_parent_account_id] ON [chart_of_accounts] ("parent_account_id")
GO

CREATE INDEX [idx_coa_account_type_id] ON [chart_of_accounts] ("account_type_id")
GO

CREATE INDEX [idx_coa_tree_path] ON [chart_of_accounts] ("tree_path")
GO

CREATE UNIQUE INDEX [currency_exchange_rates_index_22] ON [currency_exchange_rates] ("organization_id", "from_currency", "to_currency", "rate_date", "is_average_rate")
GO

CREATE UNIQUE INDEX [journal_types_index_23] ON [journal_types] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [journals_index_24] ON [journals] ("organization_id", "journal_number")
GO

CREATE INDEX [idx_journals_organization_id] ON [journals] ("organization_id")
GO

CREATE INDEX [idx_journals_journal_type_id] ON [journals] ("journal_type_id")
GO

CREATE INDEX [idx_journals_period_id] ON [journals] ("period_id")
GO

CREATE INDEX [idx_journals_status] ON [journals] ("status")
GO

CREATE INDEX [idx_journals_journal_date] ON [journals] ("journal_date")
GO

CREATE INDEX [idx_journals_source_reference] ON [journals] ("source_reference")
GO

CREATE UNIQUE INDEX [journal_lines_index_31] ON [journal_lines] ("journal_id", "line_number")
GO

CREATE INDEX [idx_journal_lines_journal_id] ON [journal_lines] ("journal_id")
GO

CREATE INDEX [idx_journal_lines_account_id] ON [journal_lines] ("account_id")
GO

CREATE INDEX [idx_journal_lines_department_id] ON [journal_lines] ("department_id")
GO

CREATE INDEX [idx_journal_lines_project_id] ON [journal_lines] ("project_id")
GO

CREATE INDEX [idx_journal_lines_cost_center_id] ON [journal_lines] ("cost_center_id")
GO

CREATE INDEX [idx_gl_organization_id] ON [general_ledger] ("organization_id")
GO

CREATE INDEX [idx_gl_account_id] ON [general_ledger] ("account_id")
GO

CREATE INDEX [idx_gl_period_id] ON [general_ledger] ("period_id")
GO

CREATE INDEX [idx_gl_transaction_date] ON [general_ledger] ("transaction_date")
GO

CREATE INDEX [idx_gl_journal_id] ON [general_ledger] ("journal_id")
GO

CREATE INDEX [idx_gl_department_id] ON [general_ledger] ("department_id")
GO

CREATE INDEX [idx_gl_project_id] ON [general_ledger] ("project_id")
GO

CREATE INDEX [idx_gl_cost_center_id] ON [general_ledger] ("cost_center_id")
GO

CREATE UNIQUE INDEX [tax_authorities_index_45] ON [tax_authorities] ("organization_id", "name")
GO

CREATE UNIQUE INDEX [tax_types_index_46] ON [tax_types] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [tax_codes_index_47] ON [tax_codes] ("organization_id", "code")
GO

CREATE INDEX [idx_tax_codes_organization_id] ON [tax_codes] ("organization_id")
GO

CREATE INDEX [idx_tax_codes_tax_type_id] ON [tax_codes] ("tax_type_id")
GO

CREATE UNIQUE INDEX [customers_index_50] ON [customers] ("organization_id", "customer_code")
GO

CREATE UNIQUE INDEX [sales_categories_index_51] ON [sales_categories] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [products_index_52] ON [products] ("organization_id", "product_code")
GO

CREATE INDEX [idx_products_organization_id] ON [products] ("organization_id")
GO

CREATE INDEX [idx_products_category_id] ON [products] ("category_id")
GO

CREATE UNIQUE INDEX [price_lists_index_55] ON [price_lists] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [price_list_items_index_56] ON [price_list_items] ("price_list_id", "product_id", "min_quantity")
GO

CREATE UNIQUE INDEX [customer_price_lists_index_57] ON [customer_price_lists] ("customer_id", "price_list_id")
GO

CREATE UNIQUE INDEX [sales_quotes_index_58] ON [sales_quotes] ("organization_id", "quote_number")
GO

CREATE UNIQUE INDEX [sales_quote_lines_index_59] ON [sales_quote_lines] ("quote_id", "line_number")
GO

CREATE UNIQUE INDEX [sales_orders_index_60] ON [sales_orders] ("organization_id", "order_number")
GO

CREATE INDEX [idx_sales_orders_organization_id] ON [sales_orders] ("organization_id")
GO

CREATE INDEX [idx_sales_orders_customer_id] ON [sales_orders] ("customer_id")
GO

CREATE INDEX [idx_sales_orders_order_date] ON [sales_orders] ("order_date")
GO

CREATE INDEX [idx_sales_orders_status] ON [sales_orders] ("status")
GO

CREATE UNIQUE INDEX [sales_order_lines_index_65] ON [sales_order_lines] ("order_id", "line_number")
GO

CREATE UNIQUE INDEX [invoices_index_66] ON [invoices] ("organization_id", "invoice_number")
GO

CREATE INDEX [idx_invoices_organization_id] ON [invoices] ("organization_id")
GO

CREATE INDEX [idx_invoices_customer_id] ON [invoices] ("customer_id")
GO

CREATE INDEX [idx_invoices_order_id] ON [invoices] ("order_id")
GO

CREATE INDEX [idx_invoices_invoice_date] ON [invoices] ("invoice_date")
GO

CREATE INDEX [idx_invoices_due_date] ON [invoices] ("due_date")
GO

CREATE INDEX [idx_invoices_status] ON [invoices] ("status")
GO

CREATE UNIQUE INDEX [invoice_lines_index_73] ON [invoice_lines] ("invoice_id", "line_number")
GO

CREATE UNIQUE INDEX [vendors_index_74] ON [vendors] ("organization_id", "vendor_code")
GO

CREATE UNIQUE INDEX [purchase_orders_index_75] ON [purchase_orders] ("organization_id", "po_number")
GO

CREATE UNIQUE INDEX [purchase_order_lines_index_76] ON [purchase_order_lines] ("po_id", "line_number")
GO

CREATE UNIQUE INDEX [vendor_bills_index_77] ON [vendor_bills] ("organization_id", "bill_number")
GO

CREATE UNIQUE INDEX [vendor_bill_lines_index_78] ON [vendor_bill_lines] ("bill_id", "line_number")
GO

CREATE UNIQUE INDEX [warehouses_index_79] ON [warehouses] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [inventory_locations_index_80] ON [inventory_locations] ("warehouse_id", "code")
GO

CREATE UNIQUE INDEX [inventory_items_index_81] ON [inventory_items] ("organization_id", "product_id", "warehouse_id", "batch_number", "serial_number")
GO

CREATE INDEX [idx_inventory_items_product_id] ON [inventory_items] ("product_id")
GO

CREATE INDEX [idx_inventory_items_warehouse_id] ON [inventory_items] ("warehouse_id")
GO

CREATE INDEX [idx_inventory_transactions_product_id] ON [inventory_transactions] ("product_id")
GO

CREATE INDEX [idx_inventory_transactions_transaction_date] ON [inventory_transactions] ("transaction_date")
GO

CREATE INDEX [idx_inventory_transactions_reference_type_id] ON [inventory_transactions] ("reference_type", "reference_id")
GO

CREATE UNIQUE INDEX [departments_index_87] ON [departments] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [cost_centers_index_88] ON [cost_centers] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [projects_index_89] ON [projects] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [payment_methods_index_90] ON [payment_methods] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [payment_terms_index_91] ON [payment_terms] ("organization_id", "code")
GO

CREATE UNIQUE INDEX [customer_payments_index_92] ON [customer_payments] ("organization_id", "payment_number")
GO

CREATE UNIQUE INDEX [payment_allocations_index_93] ON [payment_allocations] ("payment_id", "invoice_id")
GO

CREATE UNIQUE INDEX [vendor_payments_index_94] ON [vendor_payments] ("organization_id", "payment_number")
GO

CREATE UNIQUE INDEX [vendor_payment_allocations_index_95] ON [vendor_payment_allocations] ("payment_id", "bill_id")
GO

CREATE INDEX [idx_activity_logs_organization_id] ON [activity_logs] ("organization_id")
GO

CREATE INDEX [idx_activity_logs_user_id] ON [activity_logs] ("user_id")
GO

CREATE INDEX [idx_activity_logs_activity_date] ON [activity_logs] ("activity_date")
GO

CREATE INDEX [idx_activity_logs_entity_type_id] ON [activity_logs] ("entity_type", "entity_id")
GO

CREATE UNIQUE INDEX [report_definitions_index_100] ON [report_definitions] ("organization_id", "report_code")
GO

CREATE UNIQUE INDEX [system_settings_index_101] ON [system_settings] ("setting_key")
GO

CREATE UNIQUE INDEX [organization_settings_index_102] ON [organization_settings] ("organization_id", "setting_key")
GO

CREATE UNIQUE INDEX [notification_templates_index_103] ON [notification_templates] ("organization_id", "code", "notification_type")
GO

CREATE INDEX [idx_user_notifications_user_id] ON [user_notifications] ("user_id")
GO

CREATE INDEX [idx_user_notifications_status] ON [user_notifications] ("status")
GO

CREATE INDEX [idx_user_notifications_created_at] ON [user_notifications] ("created_at")
GO

CREATE UNIQUE INDEX [document_categories_index_107] ON [document_categories] ("organization_id", "name", "parent_category_id")
GO

CREATE INDEX [idx_documents_organization_id] ON [documents] ("organization_id")
GO

CREATE INDEX [idx_documents_category_id] ON [documents] ("category_id")
GO

CREATE INDEX [idx_documents_related_entity] ON [documents] ("related_entity_type", "related_entity_id")
GO

CREATE UNIQUE INDEX [udf_entity_types_index_111] ON [udf_entity_types] ("organization_id", "entity_name")
GO

CREATE UNIQUE INDEX [udf_field_groups_index_112] ON [udf_field_groups] ("organization_id", "entity_type_id", "name")
GO

CREATE UNIQUE INDEX [udf_field_definitions_index_113] ON [udf_field_definitions] ("organization_id", "entity_type_id", "field_name")
GO

CREATE UNIQUE INDEX [udf_field_options_index_114] ON [udf_field_options] ("field_id", "option_value")
GO

CREATE UNIQUE INDEX [udf_field_references_index_115] ON [udf_field_references] ("field_id")
GO

CREATE UNIQUE INDEX [udf_field_values_index_116] ON [udf_field_values] ("field_id", "entity_id")
GO

CREATE INDEX [udf_field_values_index_117] ON [udf_field_values] ("entity_id")
GO

CREATE INDEX [udf_field_values_index_118] ON [udf_field_values] ("field_id")
GO

CREATE UNIQUE INDEX [udf_multi_select_values_index_119] ON [udf_multi_select_values] ("value_id", "option_id")
GO

CREATE UNIQUE INDEX [udf_field_layouts_index_120] ON [udf_field_layouts] ("organization_id", "entity_type_id", "layout_type", "name")
GO

CREATE UNIQUE INDEX [udf_field_layout_items_index_121] ON [udf_field_layout_items] ("layout_id", "field_id")
GO

CREATE UNIQUE INDEX [udf_field_dependencies_index_122] ON [udf_field_dependencies] ("field_id", "dependent_field_id", "condition_type")
GO

CREATE UNIQUE INDEX [udf_calculated_fields_index_123] ON [udf_calculated_fields] ("field_id")
GO

CREATE UNIQUE INDEX [udf_field_permissions_index_124] ON [udf_field_permissions] ("organization_id", "field_id", "role_id")
GO

ALTER TABLE [udf_entity_types] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_groups] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_groups] ADD FOREIGN KEY ([entity_type_id]) REFERENCES [udf_entity_types] ([entity_type_id])
GO

ALTER TABLE [udf_field_definitions] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_definitions] ADD FOREIGN KEY ([entity_type_id]) REFERENCES [udf_entity_types] ([entity_type_id])
GO

ALTER TABLE [udf_field_definitions] ADD FOREIGN KEY ([field_group_id]) REFERENCES [udf_field_groups] ([field_group_id])
GO

ALTER TABLE [udf_field_options] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_references] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_references] ADD FOREIGN KEY ([reference_entity_type_id]) REFERENCES [udf_entity_types] ([entity_type_id])
GO

ALTER TABLE [udf_field_values] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_values] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_multi_select_values] ADD FOREIGN KEY ([value_id]) REFERENCES [udf_field_values] ([value_id])
GO

ALTER TABLE [udf_multi_select_values] ADD FOREIGN KEY ([option_id]) REFERENCES [udf_field_options] ([option_id])
GO

ALTER TABLE [udf_field_visibility_rules] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_visibility_rules] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_visibility_rules] ADD FOREIGN KEY ([condition_field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_layouts] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_layouts] ADD FOREIGN KEY ([entity_type_id]) REFERENCES [udf_entity_types] ([entity_type_id])
GO

ALTER TABLE [udf_field_layout_items] ADD FOREIGN KEY ([layout_id]) REFERENCES [udf_field_layouts] ([layout_id])
GO

ALTER TABLE [udf_field_layout_items] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_dependencies] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_dependencies] ADD FOREIGN KEY ([dependent_field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_calculated_fields] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_history] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_history] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [udf_field_permissions] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [udf_field_permissions] ADD FOREIGN KEY ([field_id]) REFERENCES [udf_field_definitions] ([field_id])
GO

ALTER TABLE [tenant_subscriptions] ADD FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([tenant_id])
GO

ALTER TABLE [tenant_config] ADD FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([tenant_id])
GO

ALTER TABLE [organizations] ADD FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([tenant_id])
GO

ALTER TABLE [organization_addresses] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [organization_contacts] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [users] ADD FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([tenant_id])
GO

ALTER TABLE [user_profiles] ADD FOREIGN KEY ([user_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [roles] ADD FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([tenant_id])
GO

ALTER TABLE [role_permissions] ADD FOREIGN KEY ([role_id]) REFERENCES [roles] ([role_id])
GO

ALTER TABLE [role_permissions] ADD FOREIGN KEY ([permission_id]) REFERENCES [permissions] ([permission_id])
GO

ALTER TABLE [user_roles] ADD FOREIGN KEY ([user_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [user_roles] ADD FOREIGN KEY ([role_id]) REFERENCES [roles] ([role_id])
GO

ALTER TABLE [user_roles] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [user_permissions] ADD FOREIGN KEY ([user_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [user_permissions] ADD FOREIGN KEY ([permission_id]) REFERENCES [permissions] ([permission_id])
GO

ALTER TABLE [user_permissions] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [access_logs] ADD FOREIGN KEY ([tenant_id]) REFERENCES [tenants] ([tenant_id])
GO

ALTER TABLE [access_logs] ADD FOREIGN KEY ([user_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [fiscal_years] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [fiscal_years] ADD FOREIGN KEY ([closed_by]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [accounting_periods] ADD FOREIGN KEY ([fiscal_year_id]) REFERENCES [fiscal_years] ([fiscal_year_id])
GO

ALTER TABLE [accounting_periods] ADD FOREIGN KEY ([closed_by]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [chart_of_accounts] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [chart_of_accounts] ADD FOREIGN KEY ([parent_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [chart_of_accounts] ADD FOREIGN KEY ([account_type_id]) REFERENCES [account_types] ([account_type_id])
GO

ALTER TABLE [currency_exchange_rates] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [journal_types] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [journals] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [journals] ADD FOREIGN KEY ([journal_type_id]) REFERENCES [journal_types] ([journal_type_id])
GO

ALTER TABLE [journals] ADD FOREIGN KEY ([period_id]) REFERENCES [accounting_periods] ([period_id])
GO

ALTER TABLE [journals] ADD FOREIGN KEY ([reversed_journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [journals] ADD FOREIGN KEY ([posted_by]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [journals] ADD FOREIGN KEY ([approved_by]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [journal_lines] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [journal_lines] ADD FOREIGN KEY ([account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [journal_lines] ADD FOREIGN KEY ([reconciled_by]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [general_ledger] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [general_ledger] ADD FOREIGN KEY ([account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [general_ledger] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [general_ledger] ADD FOREIGN KEY ([journal_line_id]) REFERENCES [journal_lines] ([journal_line_id])
GO

ALTER TABLE [general_ledger] ADD FOREIGN KEY ([period_id]) REFERENCES [accounting_periods] ([period_id])
GO

ALTER TABLE [tax_authorities] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [tax_types] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [tax_types] ADD FOREIGN KEY ([authority_id]) REFERENCES [tax_authorities] ([authority_id])
GO

ALTER TABLE [tax_codes] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [tax_codes] ADD FOREIGN KEY ([tax_type_id]) REFERENCES [tax_types] ([tax_type_id])
GO

ALTER TABLE [tax_codes] ADD FOREIGN KEY ([sales_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [tax_codes] ADD FOREIGN KEY ([purchase_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [customers] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [customers] ADD FOREIGN KEY ([gl_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [customer_contacts] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [customer_addresses] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [sales_categories] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [sales_categories] ADD FOREIGN KEY ([parent_category_id]) REFERENCES [sales_categories] ([category_id])
GO

ALTER TABLE [products] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [products] ADD FOREIGN KEY ([category_id]) REFERENCES [sales_categories] ([category_id])
GO

ALTER TABLE [products] ADD FOREIGN KEY ([tax_code_id]) REFERENCES [tax_codes] ([tax_code_id])
GO

ALTER TABLE [products] ADD FOREIGN KEY ([income_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [products] ADD FOREIGN KEY ([expense_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [products] ADD FOREIGN KEY ([inventory_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [price_lists] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [price_list_items] ADD FOREIGN KEY ([price_list_id]) REFERENCES [price_lists] ([price_list_id])
GO

ALTER TABLE [price_list_items] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [customer_price_lists] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [customer_price_lists] ADD FOREIGN KEY ([price_list_id]) REFERENCES [price_lists] ([price_list_id])
GO

ALTER TABLE [sales_quotes] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [sales_quotes] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [sales_quotes] ADD FOREIGN KEY ([customer_contact_id]) REFERENCES [customer_contacts] ([contact_id])
GO

ALTER TABLE [sales_quotes] ADD FOREIGN KEY ([price_list_id]) REFERENCES [price_lists] ([price_list_id])
GO

ALTER TABLE [sales_quotes] ADD FOREIGN KEY ([shipping_address_id]) REFERENCES [customer_addresses] ([address_id])
GO

ALTER TABLE [sales_quotes] ADD FOREIGN KEY ([billing_address_id]) REFERENCES [customer_addresses] ([address_id])
GO

ALTER TABLE [sales_quote_lines] ADD FOREIGN KEY ([quote_id]) REFERENCES [sales_quotes] ([quote_id])
GO

ALTER TABLE [sales_quote_lines] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [sales_quote_lines] ADD FOREIGN KEY ([tax_code_id]) REFERENCES [tax_codes] ([tax_code_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([customer_contact_id]) REFERENCES [customer_contacts] ([contact_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([quote_id]) REFERENCES [sales_quotes] ([quote_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([price_list_id]) REFERENCES [price_lists] ([price_list_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([shipping_address_id]) REFERENCES [customer_addresses] ([address_id])
GO

ALTER TABLE [sales_orders] ADD FOREIGN KEY ([billing_address_id]) REFERENCES [customer_addresses] ([address_id])
GO

ALTER TABLE [sales_order_lines] ADD FOREIGN KEY ([order_id]) REFERENCES [sales_orders] ([order_id])
GO

ALTER TABLE [sales_order_lines] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [sales_order_lines] ADD FOREIGN KEY ([tax_code_id]) REFERENCES [tax_codes] ([tax_code_id])
GO

ALTER TABLE [sales_order_lines] ADD FOREIGN KEY ([quote_line_id]) REFERENCES [sales_quote_lines] ([quote_line_id])
GO

ALTER TABLE [invoices] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [invoices] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [invoices] ADD FOREIGN KEY ([order_id]) REFERENCES [sales_orders] ([order_id])
GO

ALTER TABLE [invoices] ADD FOREIGN KEY ([billing_address_id]) REFERENCES [customer_addresses] ([address_id])
GO

ALTER TABLE [invoices] ADD FOREIGN KEY ([shipping_address_id]) REFERENCES [customer_addresses] ([address_id])
GO

ALTER TABLE [invoices] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [invoice_lines] ADD FOREIGN KEY ([invoice_id]) REFERENCES [invoices] ([invoice_id])
GO

ALTER TABLE [invoice_lines] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [invoice_lines] ADD FOREIGN KEY ([tax_code_id]) REFERENCES [tax_codes] ([tax_code_id])
GO

ALTER TABLE [invoice_lines] ADD FOREIGN KEY ([order_line_id]) REFERENCES [sales_order_lines] ([order_line_id])
GO

ALTER TABLE [vendors] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [vendors] ADD FOREIGN KEY ([gl_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [vendor_contacts] ADD FOREIGN KEY ([vendor_id]) REFERENCES [vendors] ([vendor_id])
GO

ALTER TABLE [vendor_addresses] ADD FOREIGN KEY ([vendor_id]) REFERENCES [vendors] ([vendor_id])
GO

ALTER TABLE [purchase_orders] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [purchase_orders] ADD FOREIGN KEY ([vendor_id]) REFERENCES [vendors] ([vendor_id])
GO

ALTER TABLE [purchase_orders] ADD FOREIGN KEY ([vendor_contact_id]) REFERENCES [vendor_contacts] ([contact_id])
GO

ALTER TABLE [purchase_orders] ADD FOREIGN KEY ([delivery_address_id]) REFERENCES [organization_addresses] ([address_id])
GO

ALTER TABLE [purchase_order_lines] ADD FOREIGN KEY ([po_id]) REFERENCES [purchase_orders] ([po_id])
GO

ALTER TABLE [purchase_order_lines] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [purchase_order_lines] ADD FOREIGN KEY ([tax_code_id]) REFERENCES [tax_codes] ([tax_code_id])
GO

ALTER TABLE [vendor_bills] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [vendor_bills] ADD FOREIGN KEY ([vendor_id]) REFERENCES [vendors] ([vendor_id])
GO

ALTER TABLE [vendor_bills] ADD FOREIGN KEY ([po_id]) REFERENCES [purchase_orders] ([po_id])
GO

ALTER TABLE [vendor_bills] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [vendor_bill_lines] ADD FOREIGN KEY ([bill_id]) REFERENCES [vendor_bills] ([bill_id])
GO

ALTER TABLE [vendor_bill_lines] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [vendor_bill_lines] ADD FOREIGN KEY ([account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [vendor_bill_lines] ADD FOREIGN KEY ([tax_code_id]) REFERENCES [tax_codes] ([tax_code_id])
GO

ALTER TABLE [vendor_bill_lines] ADD FOREIGN KEY ([po_line_id]) REFERENCES [purchase_order_lines] ([po_line_id])
GO

ALTER TABLE [warehouses] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [inventory_locations] ADD FOREIGN KEY ([warehouse_id]) REFERENCES [warehouses] ([warehouse_id])
GO

ALTER TABLE [inventory_items] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [inventory_items] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [inventory_items] ADD FOREIGN KEY ([warehouse_id]) REFERENCES [warehouses] ([warehouse_id])
GO

ALTER TABLE [inventory_items] ADD FOREIGN KEY ([location_id]) REFERENCES [inventory_locations] ([location_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([product_id]) REFERENCES [products] ([product_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([from_warehouse_id]) REFERENCES [warehouses] ([warehouse_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([from_location_id]) REFERENCES [inventory_locations] ([location_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([to_warehouse_id]) REFERENCES [warehouses] ([warehouse_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([to_location_id]) REFERENCES [inventory_locations] ([location_id])
GO

ALTER TABLE [inventory_transactions] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [departments] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [departments] ADD FOREIGN KEY ([parent_department_id]) REFERENCES [departments] ([department_id])
GO

ALTER TABLE [cost_centers] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [cost_centers] ADD FOREIGN KEY ([parent_cost_center_id]) REFERENCES [cost_centers] ([cost_center_id])
GO

ALTER TABLE [projects] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [projects] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [projects] ADD FOREIGN KEY ([project_manager_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [payment_methods] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [payment_methods] ADD FOREIGN KEY ([gl_account_id]) REFERENCES [chart_of_accounts] ([account_id])
GO

ALTER TABLE [payment_terms] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [customer_payments] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [customer_payments] ADD FOREIGN KEY ([customer_id]) REFERENCES [customers] ([customer_id])
GO

ALTER TABLE [customer_payments] ADD FOREIGN KEY ([payment_method_id]) REFERENCES [payment_methods] ([payment_method_id])
GO

ALTER TABLE [customer_payments] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [payment_allocations] ADD FOREIGN KEY ([payment_id]) REFERENCES [customer_payments] ([payment_id])
GO

ALTER TABLE [payment_allocations] ADD FOREIGN KEY ([invoice_id]) REFERENCES [invoices] ([invoice_id])
GO

ALTER TABLE [vendor_payments] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [vendor_payments] ADD FOREIGN KEY ([vendor_id]) REFERENCES [vendors] ([vendor_id])
GO

ALTER TABLE [vendor_payments] ADD FOREIGN KEY ([payment_method_id]) REFERENCES [payment_methods] ([payment_method_id])
GO

ALTER TABLE [vendor_payments] ADD FOREIGN KEY ([journal_id]) REFERENCES [journals] ([journal_id])
GO

ALTER TABLE [vendor_payment_allocations] ADD FOREIGN KEY ([payment_id]) REFERENCES [vendor_payments] ([payment_id])
GO

ALTER TABLE [vendor_payment_allocations] ADD FOREIGN KEY ([bill_id]) REFERENCES [vendor_bills] ([bill_id])
GO

ALTER TABLE [activity_logs] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [activity_logs] ADD FOREIGN KEY ([user_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [report_definitions] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [scheduled_reports] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [scheduled_reports] ADD FOREIGN KEY ([report_id]) REFERENCES [report_definitions] ([report_id])
GO

ALTER TABLE [organization_settings] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [notification_templates] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [user_notifications] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [user_notifications] ADD FOREIGN KEY ([user_id]) REFERENCES [users] ([user_id])
GO

ALTER TABLE [user_notifications] ADD FOREIGN KEY ([template_id]) REFERENCES [notification_templates] ([template_id])
GO

ALTER TABLE [document_categories] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [document_categories] ADD FOREIGN KEY ([parent_category_id]) REFERENCES [document_categories] ([category_id])
GO

ALTER TABLE [documents] ADD FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [documents] ADD FOREIGN KEY ([category_id]) REFERENCES [document_categories] ([category_id])
GO

ALTER TABLE [organizations] ADD CONSTRAINT [fk_organizations_parent] FOREIGN KEY ([parent_organization_id]) REFERENCES [organizations] ([organization_id])
GO

ALTER TABLE [users] ADD CONSTRAINT [fk_users_organization] FOREIGN KEY ([organization_id]) REFERENCES [organizations] ([organization_id])
GO
