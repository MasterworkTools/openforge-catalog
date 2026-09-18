const js = require('@eslint/js');
const typescript = require('typescript-eslint');
const react = require('eslint-plugin-react');
const reactHooks = require('eslint-plugin-react-hooks');
const globals = require('globals');

// Since Next.js ESLint config doesn't support flat config yet,
// we'll define the essential rules manually
module.exports = [
  js.configs.recommended,
  ...typescript.configs.recommended,
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021,
        ...globals.node,
        React: 'readonly',
      },
      parser: typescript.parser,
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    plugins: {
      react,
      '@typescript-eslint': typescript.plugin,
      'react-hooks': reactHooks,
    },
    rules: {
      // React Hooks rules
      ...reactHooks.configs.recommended.rules,

      // React rules
      ...react.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',

      // TypeScript rules
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      }],
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
  },
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'public/**',
      '*.config.js',
      '*.config.ts',
      'coverage/**',
      'db-data/**',
      'api/**',
      'openforge/**',
      'build/**',
      'dist/**',
    ],
  },
];
