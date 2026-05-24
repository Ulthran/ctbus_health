# ctbus_health

## Active code

All active development is in `pipeline/`:

- `pipeline/listener/index.py` — Telegram webhook Lambda (receives messages, writes to S3, enqueues to SQS)
- `pipeline/processor/index.py` — SQS-triggered Lambda (parses and stores health data)
- `pipeline/terraform/` — all infrastructure (Terraform)

## Deprecated

`etl/` is deprecated. Do not modify or extend it.

## Frontend

`pipeline/frontend/` — Vue 3 + Vuetify 3 + vue3-sfc-loader (no build step). Served from S3 at `https://ctbus-health-data.s3.us-east-1.amazonaws.com/index.html`. Run locally with `python pipeline/frontend/serve.py 8081 --local`.

### Mobile-first design rules

The app is primarily used on a phone (logging food on the go). All UI work must follow these constraints:

- **Single-column layouts** — no persistent sidebars or multi-column panels on the main views. `max-width: 600px` on the Add tab.
- **Touch targets** — buttons at least 44×44px. Use `size="small"` Vuetify buttons minimally; prefer `size="default"` for primary actions.
- **No hover-only affordances** — anything interactive must be tappable without hover state.
- **Bar charts** — use CSS grid (`grid-template-columns: repeat(N, 1fr)`) for even column spacing. Keep a fixed label zone above bars and a fixed axis zone below so bars never overlap text.
- **Camera / barcode** — the scanner dialog uses `facingMode: "environment"` (back camera). Always provide a manual barcode fallback text field in the scanner dialog.
- **Autocomplete** — dropdowns must have sufficient `z-index` (200+) and use `@mousedown.prevent` on items to prevent blur-before-click race.

## Deploy

```
cd pipeline/terraform && terraform apply
```
