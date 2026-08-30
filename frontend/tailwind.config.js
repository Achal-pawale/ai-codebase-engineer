/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#090C10",
          900: "#0D1117",
          850: "#111722",
          800: "#161C29",
          700: "#1C2433",
          600: "#232C3D",
          500: "#2D3748",
        },
        ink: {
          100: "#F0F3F8",
          200: "#D7DDE8",
          300: "#AEB8C9",
          400: "#8891A3",
          500: "#69728A",
          600: "#4E5568",
        },
        accent: {
          DEFAULT: "#4C8DFF",
          dim: "#3A6BC4",
          bright: "#7FADFF",
          soft: "#17233D",
        },
        ok: {
          DEFAULT: "#3FB950",
          soft: "#0F2818",
        },
        warn: {
          DEFAULT: "#D29922",
          soft: "#2B2211",
        },
        danger: {
          DEFAULT: "#F85149",
          soft: "#2B1315",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
      },
      boxShadow: {
        panel: "0 0 0 1px rgba(255,255,255,0.04), 0 8px 24px -8px rgba(0,0,0,0.5)",
      },
      keyframes: {
        pulseDot: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(2px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "pulse-dot": "pulseDot 1.6s ease-in-out infinite",
        "fade-in": "fadeIn 0.15s ease-out",
      },
    },
  },
  plugins: [],
};
