# Krampuslauf source review

Reviewed **1 November 2026**. Input: the supplied **1.8.0-beta.2** full-source archive. Output: **1.8.0-beta.3**, with profile-recovery hardening, publication exclusions and documentation.

## Publishing assessment

No embedded game passwords, GitHub/API tokens, private keys or bundled live account settings were found in the reviewed source package. Publishing this source does not itself grant remote access to the publisher's computer.

A local file-restoration weakness was found and addressed before preparing beta.3. Use the new package for publication. This is a scoped source/package review, not a guarantee that the application, dependencies or a future Windows executable have no vulnerabilities.

## What was inspected

- All 77 files in the input ZIP were matched against the working beta.2 source. Its SHA-256 was `564df3d5af85f16af37d0e030a5f358b8e7b29ff42f65847f3a5b5ad2dcbc423`.
- Source imports and operations related to networking, process execution, elevation, file reads/writes, profile restoration, the local Razor bridge and data persistence.
- Text files for recognizable secret formats, assigned credentials, personal Windows-user paths and email addresses. No such private values were detected. Test fixtures use example data.
- Packaged files for app-data JSON, live Razor profiles, logs, saved calibration captures, environments and build output. These private/generated files were absent.
- The supplied PNG metadata: orientation, display/color metadata and an XMP identifier were present; no name, location/GPS or personal file path was found. Artwork bytes are unchanged.

The existing GitHub repository, prior commits, the author's Windows machine, installed Razor/Classic Client and a compiled release executable were not inspected. Secret scanning is imperfect; review the actual GitHub Desktop Changes list before pushing.

## Findings and changes

| Area | Finding | Beta.3 response |
| --- | --- | --- |
| Profile restoration | Recovery JSON contained arbitrary file paths that were trusted during restore. A person/process already able to alter the local record could redirect file writes or deletions when restoration was invoked, potentially with the rights of the person running Krampuslauf. | Validate the record's structure and constrain targets to `Profiles/RazorEnhanced.NewProfiles` and `Backup/RazorEnhanced.NewProfiles`. Constrain backup and completion-record paths to the expected app recovery session. Reject relative/traversal paths, network/device paths, links and Windows reparse points. Validate all backup content and checksums before restoration; bound input sizes. |
| Accidental publication | The old `.gitignore` covered Python/build output but not most private runtime files. | Added explicit settings/history, calibration, bridge-state, Razor-data/recovery, credentials/key and archive exclusions. Tested 30 representative private/generated paths; all were ignored, while intended source files remained eligible. |
| Network access | No network listener, remote-control server, telemetry uploader or in-app credential submission was found. | No network service was added. The explicit GitHub button opens the user's browser. Dependency installation downloads packages during setup/build. |
| Local bridge | Razor and Krampuslauf exchange short-lived local JSON commands. Run IDs and freshness checks reduce stale-command mistakes. | The bridge is unchanged. These files are not an authentication boundary against a malicious process running as the same Windows user. |
| Dependency/build reproducibility | Runtime requirements allow version ranges; PyInstaller is installed without a fixed version by the build script. | No unverified lockfile was invented. Record and audit the versions actually resolved on the Windows release builder before claiming a dependency audit or reproducible build. |

The restoration checks preserve legitimate schema-1 recovery records and exact-byte original backups. They deliberately refuse linked/nonlocal recovery locations. Existing interrupted normal transactions and absent Backup registries remain recoverable in the tests.

## Remaining trust and privacy limits

Krampuslauf controls mouse/keyboard input, invokes Razor actions and is intended to run elevated alongside Razor/Classic Client. Only run a trusted source/build and its dependencies. Editable Python modules or replacement DLLs in an application folder are executable code, not harmless configuration.

The profile checks do not authenticate a backup's author, make app-data files tamper-proof, or prevent every concurrent filesystem race. Someone who already controls the Windows account can still change local configuration, valid profile content or bridge messages. A complete privilege boundary would require a different architecture and Windows-specific testing.

`%LOCALAPPDATA%\Krampuslauf` can contain character/shard names, fingerprints, local history identifiers, machine paths, marker crops and original Razor profile registries. Those hashes are identifiers, not encryption. Activity logs and error details can contain personal information even though Krampuslauf does not request or store game login credentials. Do not publish that folder or an unreviewed log/screenshot.

`.gitignore` is a convenience, not a secret detector: already tracked files remain tracked, forced additions can bypass it, and ignored ZIPs can still be uploaded manually as release assets. A previously exposed credential must be revoked/rotated; removing the current file does not erase older commits. See [GitHub's ignore documentation](https://docs.github.com/en/get-started/getting-started-with-git/ignoring-files) and [sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

## Validation

- **253 tests and 19 subtests passed** in the Linux test environment after the beta.3 changes.
- New regression cases cover redirected write/delete targets, backup/archive escapes, swapped or malformed records, traversal and relative/network paths, oversized manifests, invalid backup content, symlinks and simulated Windows reparse attributes.
- Existing tests still cover profile backup/restore, interrupted restoration, bridge/route simulations, input pauses, persistent typing approval and pending-creation recovery.
- The updated Setup page renders with the 250 × 250 logo in both browser-preview themes, without measured content overflow. The supplied artwork is unchanged.
- No native Windows EXE, live input, NTFS junction behavior, full resolved dependency vulnerability scan or remote Git history audit was completed here. Those remain release checks, not implied results.

The [configuration guide](../CONFIGURATION.md) explains safe setup and recovery. The [publishing walkthrough](GITHUB_PUBLISHING.md) explains source commits, email privacy and beta release assets.
