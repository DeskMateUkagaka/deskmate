# Third-Party Notices

This project depends on third-party software.

## Qt For Python / PySide6

DeskMate uses `PySide6`, including Qt modules such as Qt Widgets, Qt WebChannel, and Qt WebEngine.

Qt for Python / PySide6 is developed and distributed by The Qt Company Ltd. and Qt contributors.

Official Qt for Python licensing documentation states that Qt for Python is available under:

- LGPLv3
- GPLv2
- GPLv3
- commercial Qt licenses

Relevant upstream documentation:

- `Licenses Used in Qt for Python`
- `Obligations of the GPL and LGPL`
- `Qt WebEngine Licensing`
- `Deploying Qt WebEngine Applications`

## Attribution

- Qt for Python / PySide6: The Qt Company Ltd. and Qt contributors
- Qt framework and Qt WebEngine: The Qt Company Ltd., Qt contributors, and the third-party projects listed by Qt and Chromium in their bundled notices

## Distribution Notes

If you distribute DeskMate binaries or installers that bundle `PySide6`, Qt shared libraries, or Qt WebEngine components, you should make sure the distribution also includes the corresponding third-party license notices and license texts required by those components.

In practice, that usually means:

- giving recipients a copy of the applicable LGPL/GPL license text for the Qt for Python community edition you ship
- making it clear that Qt / PySide6 libraries are used by the application
- including the Qt WebEngine and Chromium-related third-party notices that come with the distributed Qt / PySide6 packages
- preserving the user's ability to replace the LGPL-covered shared libraries when distributing them under the LGPL model

This repository currently documents those obligations, but packaging-specific license bundling still needs to be implemented when installer/app packaging is added.

## Direct Python Dependency Inventory

The following direct Python dependencies are currently declared in `app/requirements.txt` and were checked against the local Python 3.13 environment used for development:

| Package | Installed version | License |
| --- | --- | --- |
| `PySide6` | `6.11.0` | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` |
| `PyYAML` | `6.0.3` | `MIT` |
| `websockets` | `15.0.1` | `BSD-3-Clause` |
| `cryptography` | `46.0.5` | `Apache-2.0 OR BSD-3-Clause` |
| `pydantic` | `2.12.5` | `MIT` |
| `loguru` | `0.7.3` | `MIT` |
| `platformdirs` | `4.5.1` | `MIT` |
| `setproctitle` | `1.3.7` | `BSD-3-Clause` |
| `httpx` | `0.28.1` | `BSD-3-Clause` |

This is only the direct dependency layer. Packaged builds may also contain transitive Python dependencies, Qt shared libraries, Qt plugins, Qt WebEngine assets, and Chromium-related third-party components that need their own notices preserved.

## Packaging Compliance Checklist

When DeskMate starts shipping installers, AppImages, DMGs, ZIPs, or other redistributable bundles, verify all of the following:

1. Include `LICENSE` for DeskMate itself.
2. Include `THIRD_PARTY_NOTICES.md` in the distributed package.
3. Include the relevant upstream Qt / PySide6 license texts that match the edition being shipped.
4. Include Qt WebEngine and Chromium third-party notices from the bundled Qt / PySide6 distribution.
5. Clearly state in the app documentation or packaging notes that DeskMate uses Qt / PySide6.
6. Ship Qt as shared libraries when relying on LGPL-style distribution, not as an irreplaceable static bundle.
7. Do not block users from replacing LGPL-covered Qt libraries in the distributed installation.
8. Bundle `QtWebEngineProcess` in the location expected by Qt on each platform.
9. Bundle required Qt WebEngine resource files such as `qtwebengine_resources*.pak`, `icudtl.dat`, and `v8_context_snapshot*.bin`.
10. Bundle `qtwebengine_locales` locale data.
11. Verify the final packaged artifact still runs after being moved to a clean machine or container.
12. For macOS packaging, also verify Qt WebEngine helper signing, entitlements, and notarization requirements if applicable.
13. Audit transitive Python dependencies before release and include any additional required notices.

## Remaining Gaps

- This repository now documents the obligations, but it does not yet bundle the actual upstream Qt / Qt WebEngine notice files into a release artifact.
- The final packaging scripts do not exist yet, so release-time compliance still needs to be wired into the packaging step.
- A transitive dependency audit has not yet been captured in-repo.

This file is a project notice document, not legal advice.
