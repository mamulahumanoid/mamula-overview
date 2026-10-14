# Security Policy

MAMULA is an embodied AI and physical robot runtime. Security issues may affect
software integrity, private memory, voice/video data, robot motion, hardware
commands, or operator safety. Treat suspected vulnerabilities conservatively.

## Supported Versions

This project is pre-1.0. Security fixes target the latest `main` branch unless a
release branch is explicitly marked as supported by the maintainers.

## Reporting a Vulnerability

Do not disclose exploitable details in a public issue.

Preferred reporting path:

1. Use GitHub private vulnerability reporting if it is enabled for this
   repository.
2. If private reporting is not enabled, contact the maintainers through a
   private channel listed on the repository owner profile.
3. If no private channel is available, open a public issue that only says you
   need a security contact. Do not include reproduction steps, secrets, logs, or
   private user data in that issue.

Please include, when safe to share privately:

- affected commit, branch, or release;
- vulnerable component or path;
- impact summary;
- minimal reproduction;
- whether hardware, simulation, voice, memory, or model artifacts are involved;
- any known mitigations.

## Physical Robot Safety

Issues that can cause unsafe motion, unsafe actuator commands, disabled
watchdogs, bypassed stop paths, or invalid safety envelopes are treated as
security-sensitive even if they are not traditional remote code execution bugs.

Never test suspected motion-safety vulnerabilities on a real robot without:

- an operator present;
- a reachable emergency stop;
- reduced power or a safe fixture where possible;
- a bounded test area;
- logs stored outside the public repository.

## AI Memory and Data Security

Do not attach raw memory databases, conversation logs, voice recordings, camera
frames, biometric embeddings, household maps, model weights, or training
datasets to public issues or pull requests.

Use redacted synthetic examples. If a private artifact is necessary for triage,
coordinate a private transfer path with the maintainers.

Prompt-time memory context/profile rendering is expected to keep common
secrets and contact details redacted by default. Keep
`CORE_CHAT_MEMORY_PROMPT_PRIVACY=1` for public demos, shared logs, and CI
evidence runs.

## Secrets

Never commit API keys, robot credentials, device tokens, private endpoints,
operator identities, or vendor SDK secrets. If a secret is exposed:

1. revoke it immediately;
2. rotate any downstream credentials;
3. remove it from local runtime state;
4. report the exposure privately.

Protected topic and replay HMAC keys, including
`HUMANOID_TOPIC_SECURITY_HMAC_KEY` and `HUMANOID_REPLAY_HMAC_KEY`, are runtime
secrets. Do not store them in the source tree, demo artifacts, CI logs, or
public replay reports.

`mamula security-audit` includes a runtime secret hygiene check for these keys.
The check reports file and line metadata only; it must not print the secret
literal itself.

When HMAC keys are configured, use high-entropy runtime values. Placeholder,
test-only, very short, or low-diversity values fail the
`runtime_hmac_key_strength` security gate.

For production or public demo signoff, run
`mamula security-audit --profile public-demo --session <demo.jsonl>` so both
topic/replay HMAC keys and a public demo replay session are mandatory rather
than optional. The `public_demo_signoff` section must be PASS before sharing
the demo evidence publicly.
Use `--signoff-out <path>.md` to write a shareable Markdown signoff summary
alongside the JSON evidence report.

## Security Baseline

Before reporting a regression, please run:

```bash
python -m core.tools.source_release_hygiene --tracked --staged
python -m core.tools.security_evidence_gate
python -m pytest -q
```

For hardware or HIL issues, include the relevant safety gate output when it is
safe and redacted.
