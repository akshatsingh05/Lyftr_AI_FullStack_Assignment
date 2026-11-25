/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F5F5F2",
        surface: "#FFFFFF",
        ink: { DEFAULT: "#1E2227", soft: "#5B6168", faint: "#8B9097" },
        line: "#E3E3DE",
        accent: { DEFAULT: "#245C5A", soft: "#E4EEED", ink: "#1B4644" },
        amber: { soft: "#F6EEDC", ink: "#7A5A12" },
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"],
        serif: ['"Newsreader"', "Georgia", "ui-serif", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
