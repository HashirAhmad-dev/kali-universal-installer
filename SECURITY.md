# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for a security problem.

Use GitHub's private vulnerability reporting
([Security → Report a vulnerability](https://github.com/HashirAhmad-dev/kali-universal-installer/security/advisories/new)),
or email **hashirahmad8055@gmail.com** with:

- what an attacker can do,
- the class of problem (not a working exploit),
- affected version and environment.

You will get an acknowledgement within a few days.

## Trust model

KUPI is a convenience wrapper around commands you would otherwise run yourself.
It is worth being explicit about what that means:

- KUPI runs the **installer you dropped on it**. `.run` / `.bin` / `.sh` payloads
  are arbitrary code; `.deb` / `.rpm` maintainer scripts run as root. KUPI shows
  the command and asks before running anything, but it does not sandbox or vet the
  package.
- Privilege escalation goes through **`pkexec`** (polkit). KUPI never handles your
  password.
- Root steps are wrapped as `pkexec sh -c 'cd "$1"; shift; exec "$@"' …`. The
  arguments are passed as a fixed argv (no shell interpolation of file contents),
  and paths are resolved to absolute form before use.
- Archives are extracted to a private `mktemp` directory and removed after the
  install chain finishes.
- **Cancelling** a `pkexec` step kills the wrapper, not the privileged child it
  already spawned — a root `apt`/`dpkg` may run to completion. KUPI states this in
  the log.

In scope for a report: command injection into a plan, a path that escapes the
extraction directory, privilege escalation beyond the step the user approved, or a
plan that runs something the UI did not disclose.
