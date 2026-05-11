import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "chrome-*/**",
      "edge-*/**",
      ".tooling/**",
      "*.log",
      "*.html",
    ],
  },
  ...nextVitals,
  {
    rules: {
      "@next/next/no-img-element": "off",
      "import/no-anonymous-default-export": "off",
      "react-hooks/immutability": "off",
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

export default eslintConfig;
