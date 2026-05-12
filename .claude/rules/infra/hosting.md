---
paths:
  - "**/Dockerfile"
  - "docker-compose*.yaml"
  - "docker-compose*.yml"
  - "frontend/vercel.json"
  - "backend/railway.*"
  - ".github/workflows/**"
---

# Hosting topology

Production deployment shape. Loads when touching container, compose,
Vercel, Railway, or CI config.

- **Frontend:** Vercel (Next.js native; SSG + edge caching, event-driven
  revalidation on ingestion-apply).
- **Backend:** Railway (Python, Dockerfile build). Deploys two processes
  from one image: FastAPI HTTP service (uvicorn) and the async ingestion
  worker. The HTTP service is reachable from Vercel via private network
  or authenticated public URL; the worker is internal-only.
- **Database:** Neon Postgres (serverless, branching for evals). Only the
  backend connects.

Local Docker Compose is a dev-parity shape, not the deployment topology.
The `frontend/Dockerfile` exists for parity testing; Vercel builds Next.js
itself.
