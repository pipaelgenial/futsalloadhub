import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import importPlugin from "eslint-plugin-import";

export default [
  { ignores: ["build/**", "node_modules/**", "public/**"] },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
      globals: {
        window: "readonly",
        document: "readonly",
        navigator: "readonly",
        localStorage: "readonly",
        console: "readonly",
        process: "readonly",
        fetch: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        URL: "readonly",
        FormData: "readonly",
        Blob: "readonly",
        Event: "readonly",
        HTMLElement: "readonly",
        File: "readonly",
        FileReader: "readonly",
        alert: "readonly",
        confirm: "readonly",
        Image: "readonly",
        atob: "readonly",
        btoa: "readonly",
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "jsx-a11y": jsxA11y,
      import: importPlugin,
    },
    settings: { react: { version: "detect" } },
    rules: {
      // React (mirror eslint-plugin-react recommended core rules that we actually want)
      ...react.configs.recommended.rules,
      "react/jsx-uses-react": "off",
      "react/jsx-uses-vars": "error",
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react/no-unescaped-entities": "off",
      "react/display-name": "off",
      // Hooks
      "react-hooks/rules-of-hooks": "error",
      // exhaustive-deps disabled: many useEffect calls intentionally have stable
      // closures and re-running them would cause loops. The rule is too noisy
      // for our patterns. We rely on code reviews + manual testing instead.
      "react-hooks/exhaustive-deps": "off",
      // General
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "no-console": "off",
      "no-empty": ["error", { allowEmptyCatch: true }],
    },
  },
  {
    // shadcn/ui components are vendored — relax rules
    files: ["src/components/ui/**/*.{js,jsx}", "src/hooks/use-toast.js"],
    rules: {
      "react/no-unknown-property": "off",
      "no-unused-vars": "off",
    },
  },
];
