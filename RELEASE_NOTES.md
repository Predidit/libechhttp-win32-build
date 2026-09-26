Precompiled dependency SDK for win32.

- libcurl 8.22.0 with ECH and gzip/deflate decoding enabled.
- Static zlib 1.3.2 with pinned source digest, matching headers, and license.
- Gzip runtime probes and packaged consumer link checks.
- BoringSSL cff1385e77b9b2095558fa625b3c35d589ffe09b.
- Targets: `windows-x64`, `windows-arm64`, `windows-ia32`.
- Includes static libraries, matching headers, CMake imported targets, licenses,
  build metadata and SHA-256 checksums.
- Consumers compile their own bridge and statically link these dependencies.

See README.md for compiler/runtime baselines. Pin archive SHA-256 in consumers;
do not download an unpinned latest release.
