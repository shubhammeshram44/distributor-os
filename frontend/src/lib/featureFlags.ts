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
};
