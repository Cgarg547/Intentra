# Technologies and disclosures

| Area | Actual technology | Disclosure |
| --- | --- | --- |
| Web | Next.js 16.4.3, React 19.3.0, TypeScript, Tailwind CSS 4, Lucide, Recharts | UI routes run locally; mocked browser specs intercept API traffic. |
| API | Python 3.14, FastAPI 0.162.0, SQLAlchemy 2.1.6, Alembic 1.20.1, PostgreSQL 17 | PostgreSQL is required for stateful operation; offline checks block connections. |
| AI | Local Ollama 0.35.1 with qwen3:4b | Extracts structured facts from explicit input; it does not authorize payment or implement product discovery. |
| Payments | Direct PayPal Sandbox REST Orders integration via HTTPX 0.28.1 | OAuth/order/capture operations require separate owner authorization. No real-money flow is supported or claimed. |
| Quality | pytest, Playwright, ESLint, TypeScript, GitHub Actions YAML | Local/offline results must not be represented as remote CI or provider-backed proof. |

No optional sponsor integration should be claimed unless separately implemented
and evidenced. PayPal is the sponsor integration described here; use of its name
does not imply endorsement.
