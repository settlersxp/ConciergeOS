# Frontend Development Guide

> Development commands and scripts for the ConciergeOS frontend.

## Prerequisites

- Node.js 18+
- npm (comes with Node.js)

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

## Available Scripts

| Script | Command | Description |
|--------|---------|-------------|
| Development | `npm run dev` | Start Vite dev server with hot reload |
| Build | `npm run build` | Build for production (type check + bundle) |
| Preview | `npm run preview` | Preview production build locally |
| Lint | `npm run lint` | Run oxlint for code quality checks |

## Project Structure

```
frontend/
├── public/                     # Static assets
│   ├── favicon.svg             # Site favicon
│   └── icons.svg               # SVG sprite sheet
├── src/
│   ├── main.tsx                # React entry point
│   ├── App.tsx                 # Router configuration
│   ├── App.css                 # App-level styles
│   ├── index.css               # Global styles (Tailwind)
│   ├── components/             # Reusable components
│   │   ├── Header.tsx          # Navigation header
│   │   └── ui/                 # UI primitives
│   │       ├── Badge.tsx
│   │       ├── Button.tsx
│   │       ├── Card.tsx
│   │       ├── Input.tsx
│   │       ├── Textarea.tsx
│   │       ├── Select.tsx
│   │       └── ... (20+ components)
│   ├── pages/                  # Page components
│   │   ├── Reservations.tsx    # Reservations dashboard
│   │   ├── GuestSearch.tsx     # AI guest search
│   │   ├── PerformanceTesting.tsx
│   │   ├── PerformanceDashboard.tsx
│   │   ├── Settings.tsx
│   │   ├── PromptManagement.tsx
│   │   ├── PromptGroups.tsx
│   │   └── components/         # Page-specific components
│   ├── services/               # API clients
│   │   ├── api.ts              # Main API client
│   │   ├── promptsApi.ts       # Prompts API
│   │   └── promptGroupsApi.ts  # Prompt groups API
│   ├── hooks/                  # Custom React hooks
│   │   ├── usePromptData.ts    # Prompt data fetching
│   │   └── index.ts
│   ├── context/                # React context providers
│   │   └── SettingsContext.tsx # Settings provider
│   ├── types/                  # TypeScript type definitions
│   │   ├── index.ts
│   │   ├── placeholder.ts
│   │   └── prompt.ts
│   └── utils/                  # Utility functions
│       └── diff.ts             # Diff utilities
├── index.html                  # HTML entry point
├── package.json                # Dependencies & scripts
├── vite.config.ts              # Vite configuration
├── tsconfig.json               # TypeScript configuration
├── tailwind.config.*           # Tailwind CSS configuration
└── .oxlintrc.json              # Oxlint configuration
```

## Architecture

### Tech Stack

- **React 19** — UI framework
- **TypeScript** — Type safety
- **Vite 8** — Build tool and dev server
- **React Router 7** — Client-side routing
- **Tailwind CSS 4** — Utility-first CSS framework
- **Recharts** — Charting and visualization
- **Oxlint** — Fast JavaScript/TypeScript linter

### API Integration

The frontend communicates with the backend via REST API. API requests are proxied through Vite during development:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

### State Management

- **React Context** — Global settings via `SettingsContext`
- **Custom Hooks** — Data fetching via `usePromptData`
- **Local State** — Component-level state with `useState`/`useReducer`

### Custom Hooks

| Hook | Location | Purpose |
|------|----------|---------|
| `usePromptData` | `hooks/usePromptData.ts` | Fetch and manage prompt data |

### Key Components

#### UI Components (`components/ui/`)

The project uses a comprehensive set of reusable UI primitives:

| Component | Purpose |
|-----------|---------|
| `Button` | Interactive button with variants |
| `Card` | Container card component |
| `Input` / `Textarea` | Form inputs |
| `Select` | Dropdown select |
| `Badge` | Status badges |
| `Toast` | Notification toasts |
| `Modal` | Modal dialog wrapper |
| `MultiSortTable` | Multi-column sortable table |
| `PerformanceChart` | Performance visualization |
| `PromptSelector` | Prompt selection dropdown |
| `SummaryCardGrid` | Grid of summary cards |
| `GroupedDataTable` | Grouped data display |

## Development Workflow

### Adding a New Page

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation item in `src/components/Header.tsx`

### Adding a New API Endpoint

1. Define schema in `src/types/index.ts`
2. Add function to appropriate API client in `src/services/`
3. Use in components via the API client

### Styling

All styling uses Tailwind CSS utility classes. Global styles are in `src/index.css`:

```css
@import "tailwindcss";
```

## Build & Deployment

### Production Build

```bash
npm run build
```

Output is placed in `frontend/dist/`.

### Preview Build Locally

```bash
npm run preview
```

### Linting

```bash
npm run lint
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend API calls fail | Ensure backend is running on port 8000 |
| TypeScript errors | Run `npx tsc --noEmit` to check |
| Hot reload not working | Restart dev server (`npm run dev`) |
| Build fails | Check TypeScript errors first (`npm run build 2>&1`) |