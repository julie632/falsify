# Deploy Falsify on the existing droplet

These files package the current single-team prototype. The Linux/amd64 container passed a local build and both deterministic scientific cases under Docker's architecture emulation.

## Current deployment

The app was updated overnight on October 4, 2026, with cancellation cleanup, stricter audit validation, and the rehearsed evidence interface. The preceding deployment is retained as `falsify-lab:pre-overnight` for rollback.

The app is hosted on the existing `claude` droplet at [falsify.134-122-55-169.sslip.io](https://falsify.134-122-55-169.sslip.io), behind authenticated HTTPS. The target is Ubuntu 24.04, amd64, with one CPU and 2 GiB RAM. Docker and Compose were installed from Ubuntu's package repositories. The existing Claude Remote Control service remains active. No droplet resize was performed.

The deployed image is `sha256:07e791e8d9184b71d953117fc7540c0de28d43fa3277c099050c0a6cfc10c3b1`. It runs in `/opt/falsify` using the app Compose file and optional proxy overlay. The application port is limited to host loopback; the firewall permits SSH and web ports 80/443.

Verified on the actual droplet:

- HTTPS certificate validation and HTTP-to-HTTPS redirection succeed.
- Missing or incorrect demo credentials are rejected, including an unauthenticated attempt to start a live run.
- The two deliberately selected, reviewed replay exports match the laptop's verified source records exactly. These are historical runs, not fresh Linux agent runs.
- Fresh deterministic acceptance runs on the overnight image both passed: flawed case `e17a646b9bc841d8b005a406ff8d4cde` measured 98.0508% original accuracy, 21 shared participants, and completed a zero-overlap correction; clean control `89de0ed64b2e4eb690e492b68e9b50c1` measured 96.1656% accuracy and zero overlap without redundant correction.
- Cancellation during actual CPU work preserved its finished measurement, blocked a concurrent run while draining, and produced no final scientific verdict.
- Hosted HTML, JavaScript, and CSS match the source exercised in the browser rehearsal.
- A normal app restart retained the dataset and both new complete run exports unchanged. No job remains active after the acceptance checks.
- The app reports healthy, zero OOM events, and zero automatic restarts. Sampled idle working-set usage after the computation was approximately 375 MiB for the app and 23 MiB for the proxy.

**Live AI operation on the droplet is still pending the account owner's separate Codex sign-in and subsequent integration check.** A device-code login was started for that purpose. Its temporary code expires; start a new flow if necessary. Private website login details are stored locally in `output/deployment/access.txt`, excluded from Git. They are separate from the Codex account login.

The app runs as UID 10001, with one Uvicorn worker. It listens on port 8765 inside its container and is published only to `127.0.0.1:18765` on the host. An HTTPS reverse proxy with authentication for the entire site is required before giving anyone a public link.

## Inspect the existing droplet first

Confirm its OS, CPU architecture, free memory, free disk, current containers, occupied ports, firewall, reverse proxy, and domains. Check whether Docker Engine and the Compose plugin are already installed. If they are absent, choose the appropriate official installation for the detected OS before proceeding. This package does not assume Ubuntu or install Docker for you.

Useful read-only commands on a Linux host include:

```sh
uname -m
cat /etc/os-release
free -h
df -h
ss -ltnp
docker version
docker compose version
docker ps
```

Inspect the existing proxy configuration and service before adding a site. Do not overwrite other applications, reuse an occupied port, open the app port publicly, or restart unrelated services. The included Caddy template works with a **host-installed Caddy** proxy or the optional Linux host-network proxy overlay described below. An ordinary bridge-network proxy container has a separate loopback interface; do not point that configuration at its own `127.0.0.1`.

The default application memory limit is 1 GiB and the CPU limit is one core. Python's numerical libraries use one computation thread. The local Linux/amd64 deterministic validation reached approximately 340 MiB in sampled Docker working-set usage and 442.2 MiB in kernel peak charged memory, with no OOM events. These measurements exclude live agent inference. The inspected droplet has 2 GiB RAM and an existing service using about 1.1 GiB; preserve that service and measure live-run memory before treating the proposed limit as sufficient.

## Package and build

Transfer only reviewed source and deployment files. The image build admits only the Python application modules, agent YAML, three frontend files, project metadata, and dependency lock. The Dockerfile copies those paths explicitly and `.dockerignore` denies all other input.

Do not transfer the laptop's `.codex` directory, credentials, resume, original PDFs, `.venv`, unreviewed run history, or the entire workspace. Two selected successful public-benchmark records were separately checked and transferred for labeled replay. Docker build filtering is not a filter for an unrelated file-transfer command.

From the project root on the chosen deployment machine:

```sh
cp deploy/.env.example deploy/.env
docker compose --env-file deploy/.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yaml build
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d app
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
curl --fail http://127.0.0.1:18765/api/status
```

The image uses Python 3.12 and `uv sync --locked --no-dev`. It pins uv 0.12.2 and official `@openai/codex` 0.158.0-alpha.2.1, matching the CLI protocol version used by the local integration. This CLI version is published for Linux. It is a deliberate prerelease pin, not a claim that it is the latest stable release. Changing it requires repeating the Omnigent integration checks. Python and Node base-image tags receive upstream rebuilds; record image digests after the first successful target build if exact rollback is needed. The uv container workflow follows [Astral's documentation](https://docs.astral.sh/uv/guides/integration/docker/).

The application starts without a Codex login. Deterministic computations are available, while live mode should remain disabled until authentication is established and the service restarts.

To avoid build-time memory pressure on the shared droplet, build the `linux/amd64` image on the development machine and transfer the image archive through the authorized SSH connection. Load it on the server, then use `up -d --no-build app`. The tested image tag is `falsify-lab:0.1.0`; always identify the final image ID after the latest source build. A native arm64-only image will not match this droplet.

## Persistent storage

| Compose volume | Container path | Contents |
| --- | --- | --- |
| `dataset` | `/app/data` | Downloaded public dataset and provenance cache |
| `evidence` | `/app/artifacts` | Actual experiment records and exports |
| `auth_home` | `/home/falsify` | Dedicated container-user home, Codex login, and user caches |
| `runtime` | `/var/lib/falsify/omnigent` | Omnigent state and logs selected by `OMNIGENT_DATA_DIR` |
| `worker_cache` | `/app/.codex-tmp` | Writable Codex worker files required inside the otherwise read-only workspace |

Docker initializes new volumes from directories owned by UID 10001 in the image. The root filesystem is read-only; `/tmp` is a bounded temporary filesystem. Temporary Omnigent sessions are ephemeral, while final evidence records and configured runtime logs persist. Verify the actual log and storage paths during the target smoke test.

Compose sets `FALSIFY_DEDICATED_SERVER=1`. At startup, the dedicated container treats previously unfinished run records as interrupted, avoiding confusion if a recycled process ID happens to match a stale record. This mode assumes the single app worker exclusively owns the evidence volume.

Treat `auth_home` and `runtime` as private server storage. Do not publish them or include them in a source archive. Normal application restarts retain volumes. Do not use `docker compose down -v` when evidence or authentication needs to survive.

## Sign in separately on the server

Use the account owner's intended server identity. **Never copy the laptop's credential files into the image or droplet.** The dedicated server login is a separate step, completed by the user.

After the app is running, start the supported device-code flow in its container:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml exec app codex -c 'cli_auth_credentials_store="file"' login --device-auth
```

The account owner opens the official link and completes the code entry. A device code is a temporary authorization request; provide it only to the owner completing this specific login. Never disclose access tokens or credential files. Device-code login may require the account or workspace setting described in the [official authentication documentation](https://learn.chatgpt.com/docs/auth#login-on-headless-devices). If it is unavailable, arrange a separate server-side browser callback flow using an SSH tunnel. Do not fall back to copying local credentials.

Then check status and restart the app, because authentication readiness is cached at startup:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml exec app codex login status
docker compose --env-file deploy/.env -f deploy/compose.yaml restart app
curl --fail http://127.0.0.1:18765/api/status
```

Successful login is not proof that the account can use the agent's configured model or that Linux orchestration works. Verify those with an actual bounded live investigation after the basic application test. Subscription allowance is consumed; a per-run dollar cost is not reported.

## Add the authenticated HTTPS site

Use a domain already intended for this app and point its DNS at the inspected droplet. The proxy must be able to obtain and renew its HTTPS certificate. Keep the application on loopback.

The [Caddy template](../deploy/Caddyfile.example) requires Caddy 2.8 or newer. Add its site block to the existing configuration using the host's established convention. Supply an actual domain, chosen username, and fresh bcrypt password hash. Generate the hash interactively, so the plaintext password does not appear in command history:

```sh
caddy hash-password
```

Use a long random password stored in the team's password manager. Configure the three `FALSIFY_DOMAIN`, `FALSIFY_BASIC_AUTH_USER`, and `FALSIFY_BASIC_AUTH_HASH` values in the **host Caddy service's** private environment, or substitute them directly into a protected site file. Compose's `.env` does not configure a host service. Preserve dollar characters in the bcrypt hash when editing or quoting it.

The `basic_auth` directive has no path matcher, so it covers the UI, all API routes, documentation, and evidence downloads. Caddy requires a hashed password and HTTPS is needed for Basic Authentication. [Caddy's documentation](https://caddyserver.com/docs/caddyfile/directives/basic_auth) describes both requirements.

Validate the complete existing Caddy configuration with the intended environment before reloading it. Use the host's established reload method, and verify existing sites still work. The template's upstream is fixed to `127.0.0.1:18765`; if the Compose host port changes, update that upstream too.

### Optional proxy container for the inspected Linux host

The separate [proxy overlay](../deploy/compose.proxy.yaml) is for a host confirmed to have no existing proxy or conflicting listeners on ports 80 and 443. It uses a digest-pinned official Caddy image and Linux host networking, so the upstream `127.0.0.1:18765` reaches the loopback app port. It does not require host-installed Caddy.

Create `deploy/Caddyfile` as a private file with the actual hostname, username, and password hash substituted directly. The overlay does not inject the template's environment variables. Keep this file out of Git and the application image. Its mode should be `600`; the password itself belongs in the team's password manager. Inspect and allow the required public HTTPS ports using the host's existing firewall policy before starting the proxy.

From the project root, after the image is loaded and the private proxy file is ready:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.proxy.yaml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.proxy.yaml run --rm --no-deps proxy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose --env-file deploy/.env -f deploy/compose.yaml -f deploy/compose.proxy.yaml up -d --no-build app proxy
```

The proxy's separate named volumes retain certificates and configuration state. Use only this overlay on the inspected Linux host; do not assume its host-network behavior matches Docker Desktop.

## Local packaging validation

The `linux/amd64` image was built with locked Python dependencies and the exact Codex pin. The image starts as UID 10001, resolves its home to `/home/falsify`, contains no root-level source PDFs or copied Codex authentication, and reports sign-in required. Compose configuration and the example Caddy site passed validation with a throwaway test hash.

Both deterministic cases completed inside the container with real computations. The flawed run had 21 shared participants and 98.0508% accuracy; its correction and the clean control had no participant overlap and 96.1656% accuracy. The Linux original result differs by one prediction from the earlier macOS result. Use each run's recorded metrics rather than presenting one machine's number as a universal constant. Live Linux sessions remain a separate validation step requiring the dedicated server login.

## Target-host acceptance checks

1. The container is healthy and runs as UID 10001. It exposes only the intended host loopback port, with one app worker.
2. No laptop credentials, resume, PDF, or private run files are present in the image. Any imported replay must be a deliberately selected, reviewed record, labeled as replay.
3. The HTTPS site returns `401` for an unauthenticated request to `/`, `/api/status`, `/api/runs`, and `/docs`. This matters because API access can trigger inference.
4. With the site credentials, the UI loads and can run the deterministic flawed case and valid control. Verify actual overlap counts and evidence exports, rather than assuming numerical results from another architecture.
5. Following the separate Codex sign-in, a live run produces real specialist delegations and scientific tool results. A failed live run remains failed. Check the final evidence and reviewer/reference agreement.
6. Restart the app and confirm that the dataset cache, authentication, and completed evidence persist. The UI labels older runs as recorded replay.

Full-site authentication makes this a restricted team demo. It does not add per-user identities, separate inference budgets, or production multi-tenant isolation. Share access only with people authorized to run experiments using the configured server account.

## Operate and roll back

Inspect only this application's logs when troubleshooting:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml logs --tail=100 app
```

Protect runtime logs because they can contain internal session metadata. Stop only this application when needed:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yaml stop app
```

For an application rollback, restore the previous reviewed image tag and recreate only `app`, preserving its volumes. Remove or disable only this app's proxy site if retiring the deployment. Existing droplet services and their proxy routes should continue running.
