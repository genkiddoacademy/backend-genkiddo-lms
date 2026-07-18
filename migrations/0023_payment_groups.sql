-- Migration 0023: Payment Groups for batch registration (multi-child, 1x payment)
-- Creates payment_groups table and adds payment_group_id FK to registrations

-- 1. Create payment_groups table
CREATE TABLE IF NOT EXISTS payment_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID NOT NULL REFERENCES parents(id) ON DELETE CASCADE,
    total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    service_fee DOUBLE PRECISION DEFAULT 0,
    final_total DOUBLE PRECISION DEFAULT 0,
    midtrans_order_id VARCHAR(255),
    midtrans_payload JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'expired')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add FK column to registrations
ALTER TABLE registrations ADD COLUMN IF NOT EXISTS payment_group_id UUID REFERENCES payment_groups(id);

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_payment_groups_parent_id ON payment_groups(parent_id);
CREATE INDEX IF NOT EXISTS idx_payment_groups_status ON payment_groups(status);
CREATE INDEX IF NOT EXISTS idx_registrations_payment_group_id ON registrations(payment_group_id);
