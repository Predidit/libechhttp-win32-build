# libechhttp-win32-build

Public, independent builds of the libcurl + BoringSSL static dependency SDK for
ech_http. Consumers download a versioned SDK and compile only their C++ bridge.
This repository does not contain the ech_http Dart package or application code.

Targets: `windows-x64`, `windows-arm64`, `windows-ia32`.

## Contents and compatibility

Each ZIP includes matching curl/OpenSSL headers, three static libraries,
`cmake/EchHttpDeps.cmake`, third-party licenses, and `metadata.json` with per-file
SHA-256 digests and build provenance. BoringSSL has no stable ABI: use the headers
from the same SDK. All consumers must pin the archive digest as well as the tag.
The C++ runtime is not contained in these archives; the final linker supplies it.

- Windows: MSVC 2022, Release `/MT`, no LTO. Link with the same or newer MSVC toolset.
- Linux: Ubuntu 22.04, GCC 11, glibc 2.35 and matching libstdc++ or newer.
- Android: NDK 28.2.13676358, API 21, static libc++; final libraries must retain
  16 KiB ELF LOAD alignment. Use NDK 28.2 or newer for the bridge.
- macOS: 10.15 (x64), 11 (arm64); iOS: 13 (device and simulators).

HTTP/1.1 and ECH are enabled; other protocols, compression libraries, and host
CA paths are disabled. Runtime trust roots must be provided by the consumer.
The build enables PIC, hidden visibility, and disables assembly for portability.

## Build and publish

Requires Python 3.12+, Git, CMake 3.22+, Ninja, and the target compiler/SDK.
Run `python build.py --target <target>`; outputs are written to `dist/`.
Android requires `ANDROID_NDK_HOME` pointing to the pinned NDK. Linux requires
GCC 11. Windows discovers Visual Studio through vswhere; Apple requires Xcode.

`dependencies.json` fixes the curl source SHA-256, BoringSSL commit, SDK version,
and supported targets. Builds link a probe for every target and run it on
matching native hosts to check BoringSSL/ECH feature reporting.

Push the matching `v*` tag to build all targets and publish a GitHub Release only
after every target passes. Pull requests and manual runs of the build workflow
only build. The separate `Publish verified SDK artifacts` workflow can publish
an existing build without recompiling: supply its run ID and the matching
version tag. It verifies the tagged commit, every archive and the complete target
set, then creates a new release. It refuses to overwrite an existing release.
Releases contain the ZIPs, individual digest files, and `SHA256SUMS`.
Never replace an existing release: increment the SDK version for every rebuild
or dependency/toolchain change, then update consumer URL and digest pins.

Build scripts are MIT, copyright Predidit. Upstream libraries retain the licenses
included in `licenses/`. Updating dependency versions requires a new release.
