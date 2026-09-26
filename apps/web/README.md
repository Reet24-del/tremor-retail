# Tremor Retail web

Next.js 16 + TypeScript app shell for Tremor Retail: Overview, Data sources, Signals, Signal detail, Reviews and Upload.

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
npm run lint && npx tsc --noEmit && npm run build
```

Types in `lib/types.ts` mirror `services/api/app/models/contracts.py`. The browser never calculates money values; it renders validated API objects only.
