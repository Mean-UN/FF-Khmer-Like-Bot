# Keep local and hosting data separate

Deploy code only. The repository's `.gitignore` excludes local credentials,
SQLite databases and journals, generated accounts/tokens, orders, and group data.
None of those files are currently tracked by Git.

## Git deployment

Commit and push source changes normally. On hosting, update the source checkout
while retaining its existing `.env`, database files, and runtime JSON files.
Do not force-add ignored files, copy the entire local directory to hosting,
or run `git clean -x` / `git clean -fdx` on the hosting checkout: those commands
can delete ignored production data.

Before deploying, stop the API and bot and back up production databases and
runtime JSON files. Restart them after updating code. Database migrations may
add tables/columns to the hosting database; they do not import the local database.

## ZIP deployment

Upload only a code-only archive. Extract it over the source directory without
deleting existing production files first. A raw ZIP of the entire local project
is unsafe because ZIP tools do not automatically respect `.gitignore`.

The `dist/code-only.zip` archive prepared with this change excludes Git-ignored
files. It is a snapshot, so it must be regenerated after further source changes.

## Hosting storage

The bot and API on hosting must share their own persistent database and runtime
files. If the host rebuilds/replaces the whole filesystem on each deployment,
configure persistent storage first. `.gitignore` cannot preserve files that the
hosting platform deletes during a rebuild.

Do not configure local processes to use a shared/network-mounted production
database or the production delivery API when testing. Git exclusions prevent
file uploads; they do not prevent live network requests.
