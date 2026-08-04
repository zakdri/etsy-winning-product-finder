# TrendScout browser extension

Cross-browser WXT + React client for the Etsy research backend.

## Supported builds

- Chromium build: Chrome, Microsoft Edge, Brave, Opera and other Chromium browsers.
- Firefox build: Firefox WebExtensions.
- Safari source build: create the Safari output, then package/sign it with Xcode on macOS.

## Install

```bash
cd extension
npm install
```

## Development

```bash
npm run dev
npm run dev:firefox
```

## Production builds

```bash
npm run build
npm run build:firefox
npm run zip
npm run zip:firefox
```

Chromium browsers use the same generated Chromium package. Safari requires the Apple conversion and signing workflow documented in the repository root README.

The extension never contains Etsy API credentials. It calls the local backend at `http://127.0.0.1:8765` by default.
