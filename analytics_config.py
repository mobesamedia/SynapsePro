"""Public client configuration for consented onboarding analytics.

The Supabase anon key is intentionally distributable client configuration,
not a server secret. Database Row Level Security must remain the security
boundary: the anon role should be insert-only for ``onboarding_events``.
"""

SUPABASE_ONBOARDING_URL = (
    "https://brsrxgwqncgibnvqjcuj.supabase.co/rest/v1/onboarding_events"
)
SUPABASE_PUBLIC_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJyc3J4Z3dxbmNnaWJudnFqY3VqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk0NDQyNzcsImV4cCI6MjA5NTAyMDI3N30."
    "pNosGgjiTLizTc_xChzzkP8kuQqNDtoe2YkXP6CN0Mo"
)
