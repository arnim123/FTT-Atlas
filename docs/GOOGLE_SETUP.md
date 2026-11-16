# Google Drive setup

Atlas links and creates Google Docs, Sheets, and Slides with a service account
on a Shared Drive. People sign in with their own Google accounts. The service
account is the only Drive credential the API uses.

The folder tree in Atlas is a catalog. Every file the API creates lives in one
Shared Drive folder (`GOOGLE_SHARED_DRIVE_FOLDER_ID`). Sharing inside Atlas is
copied onto that file. Bots are never added in Drive; they read through the API.

Leave `GOOGLE_MODE=fake` until the steps below are done. Fake mode keeps files
in memory so the app and the tests run without calling Google.

## 1. Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or
   select a project.
2. Enable the **Google Drive API**
   (`APIs & Services` → `Library` → `Google Drive API` → `Enable`).
   Docs, Sheets, and Slides content is read and created through Drive, including
   `text/plain` export of Docs. You do not need a separate Docs API client.

## 2. OAuth client for sign-in

User login is separate from the service account. Atlas checks a Google ID token
against `GOOGLE_CLIENT_ID`.

1. `APIs & Services` → `OAuth consent screen`. Choose **Internal** if this is a
   Workspace org. Add the app name and the support email.
2. `APIs & Services` → `Credentials` → `Create credentials` → `OAuth client ID`.
3. Application type: **Web application**.
4. Authorized JavaScript origins: the Atlas web origin, for example
   `http://localhost:5173` in development and the production origin later.
5. Copy the client ID into `GOOGLE_CLIENT_ID`.

The OAuth client does not receive Drive access. Do not add Drive scopes to the
user sign-in flow.

## 3. Service account

1. `APIs & Services` → `Credentials` → `Create credentials` → `Service account`.
2. Name it something like `atlas-drive`. Skip optional user access.
3. Open the account → `Keys` → `Add key` → `Create new key` → **JSON**.
4. Store the file outside the repo. The JSON contains a private key.

The account needs the Drive scope `https://www.googleapis.com/auth/drive`.
Atlas requests that scope itself. A narrower scope such as `drive.file` cannot
open files that were created outside Atlas.

Copy the service account email (`client_email` in the JSON). It looks like
`atlas-drive@your-project.iam.gserviceaccount.com`. People who link an existing
file must share that file with this address. The API returns the same address
when a file is not visible (`GOOGLE_NOT_SHARED`).

## 4. Shared Drive

1. In Google Drive, create a Shared Drive, for example `Atlas`.
2. Add the service account email as a **Content manager**. That role can create
   files and change their permissions. Viewer is not enough.
3. Open the folder that should hold Atlas files. The URL looks like
   `https://drive.google.com/drive/folders/FOLDER_ID`.
   Copy `FOLDER_ID` into `GOOGLE_SHARED_DRIVE_FOLDER_ID`.
   Use the Shared Drive root or a folder inside it. The id is the last path
   segment.
4. Do not put the service-account JSON key in that drive.

Files Atlas creates are owned by the Shared Drive. Atlas never removes the
service account, the file owner, or members inherited from the Shared Drive
when it syncs permissions.

## 5. Environment

Put these in `backend/.env`. Do not commit the key file or the base64 blob.

```bash
GOOGLE_MODE=live
GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
GOOGLE_SERVICE_ACCOUNT_FILE=/secure/atlas-drive.json
GOOGLE_SERVICE_ACCOUNT_B64=
GOOGLE_SERVICE_ACCOUNT_EMAIL=atlas-drive@your-project.iam.gserviceaccount.com
GOOGLE_SHARED_DRIVE_FOLDER_ID=the-folder-id
COMPANY_DOMAIN=company.com
GOOGLE_SYNC_INLINE=false
```

| Variable | Purpose |
| --- | --- |
| `GOOGLE_MODE` | `live` calls Google. Anything else, including `fake`, uses the in-memory client. |
| `GOOGLE_CLIENT_ID` | Audience for user sign-in ID tokens. |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to the JSON key. Used when it is set. |
| `GOOGLE_SERVICE_ACCOUNT_B64` | The same JSON, base64-encoded, for hosts that only accept env vars. Used when the file path is empty. |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | Shown in the not-shared error. Live mode falls back to `client_email` in the JSON. |
| `GOOGLE_SHARED_DRIVE_FOLDER_ID` | Parent folder for files Atlas creates. |
| `COMPANY_DOMAIN` | Workspace domain for an organization-wide share. If empty, the first `ALLOWED_EMAIL_DOMAINS` entry is used. |
| `GOOGLE_SYNC_INLINE` | When `true` in live mode, sharing sync finishes before the response. Default `false` runs it on a background thread. Fake mode always finishes inline. |

Encode the key on macOS with:

```bash
base64 -i /secure/atlas-drive.json | tr -d '\n'
```

Paste the one line into `GOOGLE_SERVICE_ACCOUNT_B64` and leave `GOOGLE_SERVICE_ACCOUNT_FILE` empty.

`COMPANY_DOMAIN` must be the Google Workspace domain. An organization-wide
document becomes one domain permission (`reader` or `writer` from the
document's default access). Guests are not covered by that permission; Atlas
adds each guest who has a grant as their own user. A guest whose email is
inside the Workspace domain will still match the domain permission, because
Drive cannot exclude them from it.

## 6. Link an existing file

1. In Google Drive, share the Doc, Sheet, or Slide with the service account
   email as a Viewer or Editor.
2. In Atlas, link the URL. These shapes all work:

   - `https://docs.google.com/document/d/FILE_ID/edit`
   - `https://docs.google.com/document/u/0/d/FILE_ID/view?usp=sharing`
   - `https://docs.google.com/spreadsheets/d/FILE_ID/edit#gid=0`
   - `https://docs.google.com/presentation/d/FILE_ID/preview`

3. If the service account cannot open the file, the API responds `422` with
   code `GOOGLE_NOT_SHARED` and the service account email. Share the file and
   try again.
4. Linking the same file twice responds `409` with the Atlas document id that
   already owns it.

Creating a file does not require a share step. `POST /api/v1/documents/google/create`
makes the file in the Shared Drive folder and registers it under the Atlas
folder you pick.

## 7. What sync changes

Atlas is the source of truth. After a Google document is created, its
permissions change, its department changes, it is archived, restored, or
soft-deleted, or a user's access changes, Atlas updates the Drive file:

- The owner and active admins are writers.
- Department visibility and explicit grants are expanded to individual people.
  Guests are included only when a grant says so.
- Organization visibility is a single domain permission on `COMPANY_DOMAIN`.
- Private, archived, and soft-deleted files keep only the owner and admins.
- Bots are never added.
- The service account, the file owner, and Shared Drive members are not modified.

`drive_sync_status` becomes `synced` or `failed`. `drive_sync_error` stores the
Drive error, never the document body. `POST /api/v1/documents/{id}/resync`
runs the same sync when the caller can manage the document.

The API process retries failed files once an hour while `GOOGLE_MODE=live`.
A cron job can do the same pass:

```bash
python -m app.integrations.drive_sync
```

Run that from `backend/` with the environment loaded.

Permanent delete is admin-only, session-only, and only from the archive. It
moves the Drive file to trash. A normal delete does not.

## 8. Check

Set `GOOGLE_MODE=live`, restart the API, and create a Doc from Atlas. The file
should appear in the Shared Drive folder, shared with the owner and the admins.
Archive it and confirm those extra people lose access and the service account
remains.
