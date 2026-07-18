-- Add status column to students table
ALTER TABLE students ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'preview' CHECK (status IN ('preview', 'active', 'suspended', 'archived'));

-- Backfill existing students status to 'active' if they have an active enrollment
UPDATE students SET status = 'active' WHERE id IN (SELECT DISTINCT student_id FROM enrollments WHERE status = 'active');

-- Trigger to automatically synchronize classes.filled_quota and class status based on registrations
CREATE OR REPLACE FUNCTION update_class_quota_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_max_quota INTEGER;
    v_filled_quota INTEGER;
    v_class_id UUID;
    v_old_active BOOLEAN;
    v_new_active BOOLEAN;
BEGIN
    -- Determine class_id and active states
    IF TG_OP = 'INSERT' THEN
        v_class_id := NEW.class_id;
        v_old_active := FALSE;
        v_new_active := NEW.status IN ('pending', 'paid', 'active', 'completed');
    ELSIF TG_OP = 'UPDATE' THEN
        v_class_id := NEW.class_id;
        v_old_active := OLD.status IN ('pending', 'paid', 'active', 'completed');
        v_new_active := NEW.status IN ('pending', 'paid', 'active', 'completed');
    ELSIF TG_OP = 'DELETE' THEN
        v_class_id := OLD.class_id;
        v_old_active := OLD.status IN ('pending', 'paid', 'active', 'completed');
        v_new_active := FALSE;
    END IF;

    IF v_class_id IS NOT NULL THEN
        -- Fetch current max_quota and filled_quota
        SELECT max_quota, filled_quota INTO v_max_quota, v_filled_quota 
        FROM classes WHERE id = v_class_id;
        
        IF v_max_quota IS NULL THEN
            v_max_quota := 10;
        END IF;
        IF v_filled_quota IS NULL THEN
            v_filled_quota := 0;
        END IF;

        -- Adjust filled_quota based on active transition
        IF v_new_active AND NOT v_old_active THEN
            v_filled_quota := v_filled_quota + 1;
        ELSIF NOT v_new_active AND v_old_active THEN
            v_filled_quota := GREATEST(0, v_filled_quota - 1);
        END IF;

        -- Update classes table with new filled_quota and status
        UPDATE classes 
        SET 
            filled_quota = v_filled_quota,
            status = CASE 
                WHEN v_filled_quota >= v_max_quota THEN 'full'
                WHEN v_filled_quota >= FLOOR(v_max_quota * 0.8) THEN 'almost_full'
                ELSE 'open'
            END
        WHERE id = v_class_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the trigger to registrations table
DROP TRIGGER IF EXISTS trg_update_class_quota ON registrations;
CREATE TRIGGER trg_update_class_quota
AFTER INSERT OR UPDATE OR DELETE ON registrations
FOR EACH ROW
EXECUTE FUNCTION update_class_quota_trigger();

-- Force initial sync for all classes
UPDATE classes c
SET filled_quota = (
    SELECT COUNT(*) 
    FROM registrations r 
    WHERE r.class_id = c.id 
      AND r.status IN ('pending', 'paid', 'active', 'completed')
);

UPDATE classes c
SET status = CASE 
    WHEN c.filled_quota >= c.max_quota THEN 'full'
    WHEN c.filled_quota >= FLOOR(c.max_quota * 0.8) THEN 'almost_full'
    ELSE 'open'
END;
