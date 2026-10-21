-- Create subscriptions table
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    company_id UUID REFERENCES public.companies(id) UNIQUE NOT NULL,
    status TEXT DEFAULT 'trialing', -- 'active', 'trialing', 'past_due', 'canceled'
    plan_id TEXT DEFAULT 'basic',
    current_period_end TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Function to check if a company has an active subscription
CREATE OR REPLACE FUNCTION public.is_subscription_active(p_company_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    sub_status TEXT;
    period_end TIMESTAMPTZ;
BEGIN
    SELECT status, current_period_end INTO sub_status, period_end
    FROM public.subscriptions
    WHERE company_id = p_company_id;

    IF sub_status = 'active' AND period_end > NOW() THEN
        RETURN TRUE;
    END IF;

    IF sub_status = 'trialing' AND period_end > NOW() THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;
