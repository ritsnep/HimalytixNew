-- Initialize database with extensions and settings
-- This runs on first container startup only

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- For GIN indexes

-- Set timezone
SET timezone = 'UTC';

-- Create schemas for multi-tenancy (example)
-- Actual tenant schemas created by Django migrations
CREATE SCHEMA IF NOT EXISTS public;
