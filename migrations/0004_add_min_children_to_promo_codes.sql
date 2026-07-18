-- Migration: Add min_children column to promo_codes table
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS min_children INTEGER DEFAULT 0;
