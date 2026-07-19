/**
 * Feature flags
 *
 * Simple, explicit on/off switches for functionality that isn't ready to ship
 * to real users yet. Flags default to a hardcoded value below, but can be
 * force-enabled locally/in staging via the matching NEXT_PUBLIC_* env var
 * (useful for QA without touching code).
 */

function isEnabled(envValue: string | undefined, defaultValue: boolean): boolean {
  if (envValue === "true") return true;
  if (envValue === "false") return false;
  return defaultValue;
}

export const FEATURE_FLAGS = {
  // Messages tab is still under active development (WhatsApp/portal chat threads
  // aren't production-ready yet). Keep it hidden everywhere until it's finished.
  messages: isEnabled(process.env.NEXT_PUBLIC_FEATURE_MESSAGES, false),
  // Legacy Integrations (v1) page is deprecated in favour of Integrations V2.
  // Code is intentionally kept (not deleted) in case it's needed again later —
  // this just hides it from navigation. Flip NEXT_PUBLIC_FEATURE_INTEGRATIONS_V1
  // to "true" to bring it back without a code change.
  integrationsV1: isEnabled(process.env.NEXT_PUBLIC_FEATURE_INTEGRATIONS_V1, false),
};
