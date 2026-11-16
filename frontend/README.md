# Atlas — Company Knowledge & Document Management

A complete front-end workspace built with React 18, strict TypeScript, Vite, Tailwind CSS, shadcn/ui-style Radix primitives, Lucide, React Router, TanStack Query, Zustand, Recharts, react-hook-form, Zod, and @dnd-kit integration.

## Run

Use Node.js 22 or later.

```sh
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`.

The checked-in `.env` sets `VITE_USE_MOCKS=true`. This application has no backend and makes no Google API calls. The initial session signs you in as Alex Morgan, a Super Admin, so the workspace is immediately explorable. Visit `/login` or sign out to try the login flow.

```sh
npm run typecheck  # Strict TypeScript
npm run build      # Type checking and production build
npm run preview    # Serve the production build
npm test           # API workflows and server-rendered screen checks
npm run test:e2e   # Real Chrome interaction and console checks
```

The browser smoke script starts its own Vite server on port 4173 and uses an isolated Chrome profile. It requires a locally installed Google Chrome and permission to open local ports. Override `CHROME_PATH`, `ATLAS_E2E_PORT`, or `ATLAS_CHROME_PORT` if necessary. Screenshots are saved to `test-results/`.

## Route map

| Route | Screen | Access |
| --- | --- | --- |
| `/` | Redirect to Dashboard | Signed-in users |
| `/login` | Google sign-in and demo error scenarios | Everyone |
| `/dashboard` | Scoped statistics, department chart, collections, recent uploads, most viewed | Signed-in users |
| `/documents` | Folder tree, table/grid, filters, sorting, selection, bulk actions | Signed-in users |
| `/documents?folder=erp` | Example selected folder; any folder ID is supported | According to access |
| `/documents/:id` | Document preview/editor, information, permissions, versions, related documents | According to document access |
| `/search` | Global search, filters, date range, recent searches | Signed-in users |
| `/search?q=Inventory` | Example search with highlighted matches | Results filtered by role |
| `/archive` | Archived documents/folders and restoration | Items the user can manage |
| `/users` | Users, invitations, role/department editing, account status, capability matrix | Admins; managers see their department |
| `/settings` | Department, category, and tag CRUD | Super Admin and Admin |
| `/profile` | Read-only Google identity, role, department, appearance, sign out | Signed-in users |
| `/google-preview/:id` | Local stand-in for a mock Google document | According to document access |
| `/google-preview/:id?history=1` | Explanation of mock Google version history | According to document access |
| Any other route | Not-found state with a return link | Signed-in users |

Global overlays provide the add-document drawer, folder creation/renaming, permissions, move destinations, archive/delete confirmations, mobile navigation, and the command palette.

## What works

- Responsive shell: persistent desktop navigation; a focus-trapped navigation drawer below 1024 px. Light/dark CSS-variable themes and self-hosted Inter.
- Cmd/Ctrl+K search palette, keyboard-navigable controls, visible focus, labeled inputs, skip navigation, dialog focus management, and reduced-motion support.
- Five demo identities in the development-only **View as** switcher. Navigation, visible data, and action permissions change with the role. API functions validate authorization as well as the UI.
- Recursive folders with expand/collapse, counts, restricted indicators, right-click/ellipsis menus, renaming, nested creation, moves, archive/delete, and cycle prevention.
- Document list/grid views, combined filters, sorting, pagination, selection, and bulk move/archive/delete.
- Create mock Google Docs/Sheets/Slides with a template; link a validated Google URL; upload up to 10 files with progress, type checks, and a 25 MB per-file limit.
- Shared metadata form with creatable tags, category, department, folder tree, and permissions.
- Google-style paper previews and editable mock content. Uploaded PDF/image/text previews, Office download cards, and original-file downloads.
- Uploaded version history, downloads, and restoration as a new version. Text versions restore their actual preview content, too.
- Private, Department, Organization-wide, and Custom access; per-user/department View/Edit grants; access preview; Guest warning; mock Google sync states and retry.
- Search across names, descriptions, tags, and content; highlighted snippets; match chips; filters, date ranges, sorting, archived inclusion, and recent searches.
- User invitations, role/department edits, deactivation/reactivation; taxonomy inline CRUD; archive restore/permanent deletion; profile/sign-out.
- Loading, empty, error, forbidden, and not-found states. The developer tools menu beside **View as** can fail the current screen’s next API request; **Try again** recovers it.
- AI statistics and document insights remain visibly locked for Phase 2.

## Data boundary

```
src/
  api/          Typed asynchronous data functions and mock/HTTP boundary
  components/   Shared shell, shadcn/ui-style primitives, visual helpers
  features/     Dashboard, documents, folders, viewer, search, permissions,
                users, settings, and global dialogs
  pages/        Route-level screens
  hooks/        Queries, refresh, theme, debounce, recent searches
  lib/          Permission helpers, constants, query client, utilities
  store/        Zustand authentication/role and overlay state
  types/        Shared application and API types
  mocks/        In-memory records and seed data
```

Screens never import mock records. They call `src/api/` and consume shared `src/types`. The API exposes `listFolderTree`, `listDocuments`, `getDocument`, `createFolder`, `createDocument`, `searchDocuments`, `getDashboard`, `listUsers`, permissions, versions, archives, taxonomy, and authentication operations. Requests simulate approximately 300 ms latency and return isolated copies.

To connect a backend, replace these function implementations and the session/link helpers inside `src/api/`, retaining the exported contracts. `VITE_USE_MOCKS=false` currently returns a clear configuration error rather than inventing HTTP endpoints. Server-side authorization must be implemented by the eventual backend; the current checks are a UI simulation.

## Roles and scope

| Role | Document scope | Create | User management | Settings / permanent deletion |
| --- | --- | --- | --- | --- |
| Super Admin | All documents | Yes | All roles, except changing their own account | Yes |
| Admin | All documents | Yes | Non-administrator accounts | Yes |
| Department Manager | Organization-wide, own department, explicitly shared, and own private content | Yes | Employees in their own department | No |
| Employee | Organization-wide, own department, explicitly shared, and own private content | Yes | No | No |
| Guest | Documents explicitly shared with that Guest | No | No | No |

Document owners manage their own content. Managers manage accessible content in their department. Custom Edit grants allow editing existing documents, including for Guests, but do not permit creation or administrative actions. Only administrators can permanently delete. Document permissions are explicit; moving an item preserves them. Workspace folder organization access permits contributors to add content, while folder management still requires ownership or an appropriate role.

## Mock data and assumptions

- **Brand:** “Atlas” in an “Acme Workspace”; company domain `company.com`.
- **Roles:** Super Admin, Admin, Department Manager, Employee, Guest. Managers can open User Management for their own department, resolving the request’s admin-only navigation versus manager-scoped user-management requirements.
- **Records:** 52 documents, including 3 archived; 21 nested folders; 5 departments; 12 users covering all roles; all four access levels and nine file types. Department names are Product, Engineering, People & Culture, Sales, and Operations. HR folders belong to People & Culture.
- **Persistence:** Documents, folders, permissions, versions, invitations, and settings live in memory in the current tab and reset on a full reload. The role/session, theme, and recent searches persist locally. No email is sent and no external document is created, changed, or deleted.
- **Google:** Seeded and newly created mock Google documents use an internal SPA preview so unsaved-to-a-backend data remains available. Valid linked Google URLs open their real external URL. A file ID containing `unshared` (case-insensitive) simulates missing service-account sharing. Example: `https://docs.google.com/document/d/unshared-demo/edit`. The UI shows the exact service-account instruction and copy action. Normal valid IDs simulate shared access.
- **Files:** Seeded downloads use representative valid PDF, SVG, TXT, DOCX, XLSX, and PPTX samples in `public/samples/`. New uploads use browser object URLs and preview/download the chosen file. Their content is never transmitted.
- **AI:** No AI calls, generated answers, or fabricated AI analytics. All AI features are Phase 2 placeholders.
- **Offline installation:** The build environment could not reach package registries. All available dependencies were installed from the local cache. `@dnd-kit/core` remains an optional declared dependency and is used automatically when available. If absent, Vite selects the explicitly named `src/lib/dnd-fallback.tsx` adapter, which supports native dragging, Space/Tab/Enter keyboard moves, and the same visible move workflows. On a connected machine, `npm install` installs the real package; restarting Vite selects it without application changes.

For login errors, select a scenario on `/login` and press the single sign-in button. `/login?error=domain` and `/login?error=deactivated` preselect the corresponding scenario.

## Validation

Verified in the implementation environment: `npm run build` passes strict TypeScript and produces the production bundle; `npm test` passes all 18 checks. All source component files are below 250 lines. The browser smoke scripts pass JavaScript syntax checks.

The automated suite exercises authorization, scoped queries, folder nesting/cycle rejection, document and taxonomy CRUD, bulk-action authorization, search, Guest grants and revocation, Google sharing validation, file constraints, version content restoration, invitations, account status, immutable responses, mock failure recovery, route rendering, navigation visibility, and representative download files.

The implementation environment permits builds and Node tests but rejects local listening sockets (`listen EPERM`) and headless Chrome startup. Consequently, browser console, pointer/keyboard interaction, and screenshot checks must be run using `npm run test:e2e` in a normal local environment. Server-rendered checks do not replace a real browser check.

See [FILES.md](./FILES.md) for the complete list of created project files. Generated `node_modules/`, `dist/`, TypeScript build metadata, and test artifacts are excluded from that inventory.
