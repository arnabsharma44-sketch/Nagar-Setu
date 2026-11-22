# Accessibility Report

## Automated testing

**NOT RUN.** axe-core, Playwright and Lighthouse are not installed in this workspace, so no
automated WCAG scan, contrast measurement or keyboard traversal was performed. Nothing in this
report should be read as an accessibility pass.

## Observed semantics (from the rendered accessibility tree)

| Element | Observation |
| --- | --- |
| Page language/title | `ROADGUARD AI — Road Safety Intelligence` present on every page |
| Landmarks | `banner`, `navigation`, `main` exposed |
| Login fields | Real `<label for>` pairs ("Email", "Password"); inputs expose accessible names and `required` |
| Login error | `role="alert"` container exists for failure text |
| Buttons | Named ("Sign in", "Show frame", "Zoom in/out", "Sign out") — no icon-only unlabelled buttons observed |
| Links | Descriptive text ("Review queue", "All work orders →", "Open in new tab (signed, short-lived)") |
| Tables | Header cells exposed as `columnheader`; rows/cells structured |
| Map | Leaflet exposes zoom buttons with names; the map container is focusable |
| Status messaging | Realtime state is text ("Connected (ticket-authenticated)"), not colour alone |
| Demo warning | Text banner on every page, not a tooltip or colour cue |

## Specific gaps to test before claiming compliance

1. Colour contrast of the dark command theme (amber on near-black, sky on slate) — unmeasured.
2. Keyboard order and focus visibility through the horizontal nav at 390 px.
3. Focus trapping in any modal (none opened during the audit).
4. Screen-reader announcement of live realtime updates.
5. Form error association (`aria-describedby`) on the admin forms — not inspected.
6. Target size on mobile nav items — visually small, unmeasured.

## Positive sign

The UI avoids two common failure modes seen in dashboards: it does not encode status by colour
alone, and it does not use placeholder-only inputs on the login form.

## Recommendation

Install `@axe-core/playwright` and add a route sweep before any public-sector pilot; treat this
report as a smoke observation, not a certification.
