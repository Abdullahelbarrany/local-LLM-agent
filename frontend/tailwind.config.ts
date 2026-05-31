import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      animation: {
        "bar-fill": "barFill 0.7s ease-out forwards",
      },
      keyframes: {
        barFill: {
          from: { width: "0%" },
          to: { width: "var(--bar-width)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
