/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        figtree: ["var(--font-figtree)", "sans-serif"],
        sans: ["var(--font-figtree)", "sans-serif"],
      },
      colors: {
        brand: {
          dark: "#070b14",       // Sidebar background — always dark navy in both themes (shell doesn't flip)
          darkHover: "#141d33",  // Sidebar hover states
          blue: "var(--color-accent)",       // Primary accent — emerald (dark theme) / blue (light theme)
          blueHover: "var(--color-accent-hover)",
          textMuted: "#8b96ab",  // Gray text in sidebar (shell stays constant)
        },
        dashboard: {
          bg: "var(--color-canvas)",           // Page canvas
          card: "var(--color-surface)",        // Card surface
          border: "var(--color-border)",       // Divider / hairline border
          text: "var(--color-text)",           // Main text
          surfaceHover: "var(--color-surface-hover)", // Hover state for rows / list items
          inset: "var(--color-surface-inset)", // Nested/inset cell bg (icon containers, sub-panels)
          muted: "var(--color-text-muted)",    // Secondary/muted text
        },
        // Semantic feedback colors — use these instead of raw emerald/amber/rose/blue
        // shades so success/warning/danger/info states stay visually consistent
        // across every screen and are easy to re-theme later.
        success: {
          50: "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          400: "#34d399",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
        },
        warning: {
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
        },
        danger: {
          50: "#fff1f2",
          100: "#ffe4e6",
          200: "#fecdd3",
          400: "#fb7185",
          500: "#f43f5e",
          600: "#e11d48",
          700: "#be123c",
        },
        info: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
      },
      boxShadow: {
        "glow-emerald": "0 0 0 1px rgba(16,185,129,0.15), 0 8px 24px -8px rgba(16,185,129,0.25)",
        card: "0 1px 2px rgba(0,0,0,0.4), 0 12px 32px -16px rgba(0,0,0,0.5)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
}
