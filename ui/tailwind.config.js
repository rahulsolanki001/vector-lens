/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base:    "#0F1117",
          surface: "#1A1D2E",
          raised:  "#232640",
          border:  "#2D3148",
        },
        accent: {
          DEFAULT: "#7C6AF7",
          hover:   "#9585F8",
          muted:   "#3D3572",
        },
        tx: {
          primary:   "#E2E8F0",
          secondary: "#94A3B8",
          muted:     "#64748B",
          code:      "#A5F3FC",
        },
        sev: {
          error:   "#F87171",
          warning: "#FBBF24",
          healthy: "#34D399",
          info:    "#60A5FA",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        xs:   ["11px", { lineHeight: "16px" }],
        sm:   ["13px", { lineHeight: "20px" }],
        base: ["14px", { lineHeight: "22px" }],
        lg:   ["16px", { lineHeight: "24px" }],
        xl:   ["20px", { lineHeight: "28px" }],
      },
    },
  },
  plugins: [],
};
