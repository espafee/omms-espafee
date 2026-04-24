# OMMS (Outdoor Media Management System)

## Stack
- Backend: Django + Django REST Framework
- Frontend: Next.js
- Auth: JWT
- Database: PostgreSQL

## Core Modules
- users
- inventory
- bookings
- campaigns
- poe
- billing

## Rules
- Do not use mock data unless explicitly asked
- Preserve existing business logic
- Prefer minimal, modular changes
- Always inspect current code before changing it
- Explain assumptions before coding
- Keep frontend resilient to null/undefined API fields
- Keep backend write actions permission-checked
- Add or update tests when changing business logic
- For UI work, preserve current design language
- For public/client features, default to read-only and token-based access
