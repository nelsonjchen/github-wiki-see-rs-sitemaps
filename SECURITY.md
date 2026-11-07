# Dependency security notes

The dependency refresh prepared on 2026-11-07 raises the supported Python minimum
to 3.12 and updates `uv.lock`, including the optional Pub/Sub dependencies. Use
`uv sync --locked` so builds install the reviewed versions rather than silently
rewriting the lockfile.

## Known residual cache risk

A `pip-audit` scan of the refreshed lockfile reports one remaining advisory:
[GHSA-w8v5-vhqr-4h9v / CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v)
for `diskcache` 5.6.3. There is no fixed version listed as of 2026-11-07.

DiskCache uses Python pickle to serialize cached objects. An attacker who can
write to `generator/cache` or substitute a restored cache can cause code execution
when those objects are read. This is not triggered merely by a normal GHArchive
JSON event: the attacker needs control of the local cache contents. Treat the
cache as trusted executable input, not as a safe interchange format. Do not
restore cache files supplied by untrusted contributors or external sources.

The production workflow restores its existing cache only in the default-branch
job. Pull-request regression tests use disposable temporary caches and do not
restore or upload the production cache. Replacing pickle-based persistence with
a data-only format would remove this dependency and is a separate follow-up;
this dependency refresh does not claim to fix or suppress its advisory.

## Repeating the audit

To audit all locked dependencies for the active Python/platform, including extras:

```sh
uv export --frozen --all-extras --no-emit-project --format requirements-txt -o /tmp/sitemap-requirements.txt
uvx pip-audit --require-hashes -r /tmp/sitemap-requirements.txt
```

An audit exits nonzero while the unpatched DiskCache finding remains. Advisory
feeds can change; the results above are a point-in-time dependency check, not a
claim that no other vulnerabilities exist. The repository's private Dependabot
alert list was not accessible during this preparation.
