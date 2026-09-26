# libechhttp-win32-build

Public, independent builds of the libcurl + BoringSSL + zlib static dependency SDK for
ech_http. Consumers download a versioned SDK and compile only their C++ bridge.
This repository does not contain the ech_http Dart package or application code.

Targets: `windows-x64`, `windows-arm64`, `windows-ia32`.

## Contents and compatibility

Each ZIP includes matching curl/OpenSSL/zlib headers, four static libraries,
`cmake/EchHttpDeps.cmake`, third-party licenses, and `metadata.json` with per-file
SHA-256 digests and build provenance. BoringSSL has no stable ABI: use the headers
from the same SDK. All consumers must pin the archive digest as well as the tag.
The C++ runtime is not contained in these archives; the final linker supplies it.

- Windows: MSVC 2022, Release `/MT`, no LTO. Link with the same or newer MSVC toolset.
- Linux: Ubuntu 22.04, GCC 11, glibc 2.35 and matching libstdc++ or newer.
- Android: NDK 28.2.13676358, API 21, static libc++; final libraries must retain
  16 KiB ELF LOAD alignment. Use NDK 28.2 or newer for the bridge.
- macOS: 10.15 (x64), 11 (arm64); iOS: 13 (device and simulators).

HTTP/1.1, ECH, and gzip/deflate decoding via static zlib are enabled; other
protocols, Brotli, Zstandard, and host CA paths are disabled. Runtime trust roots must be provided by the consumer.
The build enables PIC, hidden visibility, and disables assembly for portability.

## Build and publish

Requires Python 3.12+, Git, CMake 3.22+, Ninja, and the target compiler/SDK.
Run `python build.py --target <target>`; outputs are written to `dist/`.
Android requires `ANDROID_NDK_HOME` pointing to the pinned NDK. Linux requires
GCC 11. Windows discovers Visual Studio through vswhere; Apple requires Xcode.

`dependencies.json` fixes the curl/zlib source SHA-256, BoringSSL commit, SDK version,
and supported targets. Builds link a probe for every target and run it on
matching native hosts to check BoringSSL/ECH/zlib feature reporting and gzip
decoding. A separate consumer link-check verifies the packaged CMake targets.

Pushes to `main`, matching `v*` tags, pull requests, and manual runs build all
targets and verify the complete SDK set. CI has read-only repository permissions;
it never creates or changes a Release. Its `verified-sdks` artifact contains all
ZIPs, individual digest files, and `SHA256SUMS`, after checking source commit,
dependency pins, target coverage, and archive/file digests.

Publish from a local maintainer session authenticated to GitHub as **Predidit**,
so the Release is attributed to the maintainer rather than the Actions bot:

1. Check out the commit to publish. Confirm `VERSION_TAG` matches
   `dependencies.json`, and `RUN_ID` is a successful build at that exact commit.
   If the tag already exists, verify it also resolves to that commit.
2. Check the logged-in account and download the verified artifact into an empty
   `dist/` directory. Replace the placeholders with the reviewed values:
   ```sh
   gh api user --jq .login
   git rev-parse HEAD
   gh run view RUN_ID --json conclusion,headSha
   gh run download RUN_ID --name verified-sdks --dir dist
   python verify_release.py VERSION_TAG --commit FULL_COMMIT_SHA
   ```
3. Create the Release using that personal session:
   ```sh
   gh release create VERSION_TAG dist/* --target FULL_COMMIT_SHA --title VERSION_TAG --notes-file RELEASE_NOTES.md
   ```
   An existing Release is an error for this explicit publication command; do not
   overwrite it. Creating a tag may trigger another read-only build, which is
   safe even when its Release already exists.

Never replace an existing release: increment the SDK version for every rebuild
or dependency/toolchain change, then update consumer URL and digest pins.

Build scripts are MIT, copyright Predidit. Upstream libraries retain the licenses
included in `licenses/`. Updating dependency versions requires a new release.
