# UI Control Inventory

Inventory taken from the rendered accessibility trees of `/login`, `/command`, `/admin` and
`/admin/work-orders/{id}`, plus the page sources. "Tested" means a real browser action this
audit; "visible" means present and correctly labelled but not individually exercised.

## `/login`

| Control | Advertised action | Test | Result |
| --- | --- | --- | --- |
| Email field (labelled) | Collect email | tested | Typed; reactive |
| Password field (labelled) | Collect password | tested | Typed; submitted via Enter |
| Sign in button | POST `/auth/login`, redirect to `next` or `/command` | tested | Authenticated (200) |
| 5 demo account buttons | Fill the email field only | tested | Fills email; does not bypass the password |
| Error container (`role=alert`) | Show failure text | visible | Correct `role`; not triggered deliberately |
| DEMO notice | State synthetic data + password source | visible | Present |

## Command centre (shared)

| Control | Advertised action | Test | Result |
| --- | --- | --- | --- |
| Nav: Overview, Cameras, Monitoring, Videos & Jobs, Events, Hotspots, Investigations | Client navigation | tested (link targets prefetched 200) | All seven prefetch successfully |
| Upload footage | `/command/videos` upload flow | visible | Covered by API/upload tests, not clicked here |
| Review queue | `/command/incidents` | visible | — |
| "View all →" | Incident list | visible | — |
| Event row "Open" | Incident detail | visible | — |
| Map zoom in/out | Leaflet zoom | tested (rendered) | Buttons present and labelled |
| Realtime badge | Shows ticket-auth WebSocket state | tested | "Connected (ticket-authenticated)" |
| "See hotspot methodology" | Methodology text | visible | — |

## Admin portal

| Control | Advertised action | Test | Result |
| --- | --- | --- | --- |
| Nav: Departments, Contractors, Assets, Contracts, Investigations, Work orders, Analytics, Audit trail, Users & roles | Client navigation | tested (prefetch 200) | Nine links resolve |
| Sign out | Revoke session → `/login` | visible | Endpoint covered (204) |
| "All work orders →" | List | visible | — |
| Work-order row "Open" | Detail | tested | Loaded `/admin/work-orders/{id}` |
| "← Work orders" | Back to list | visible | — |
| "Show frame" (evidence) | Reveals generated frame | visible | Evidence is a demo artefact and labelled so |
| "Open in new tab (signed, short-lived)" | Signed evidence URL | visible | Signed-token scoping covered by tests |
| Work-order transition buttons | Lifecycle moves | not visible | Render only when a transition is allowed for the role; verified record showed none, which matches a terminal state |

## Controls not individually executed

Forms and modals on departments/contractors/assets/contracts/investigations, filters, sorting,
pagination and date pickers were **not** clicked through in the browser. Their API contracts are
executed by the 82-operation suite, but the UI wiring for those specific controls is
unverified. That gap is deliberate: automated Playwright was unavailable, and claiming these
controls work from source reading alone would be exactly the assumption the audit brief forbids.

## Fake/decorative controls

None found. Every visible control either navigates, submits, reveals data or carries state; no
button claims a success message that the backend did not produce.
