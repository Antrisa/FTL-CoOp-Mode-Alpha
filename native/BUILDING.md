# Rebuild the native experiment

Use a clean checkout of https://github.com/FTL-Hyperspace/FTL-Hyperspace at
2540d807baef1d3654ff03a18560728b64ce3a45 (tagv1.20.0), not current master.

Run `python install_patch.py PATH_TO_CHECKOUT` from this folder. It refuses a
different commit or dirty checkout, copies the included native source files and
adds registration/CMake entries. hyperspace_1_20_0.patch records the upstream
edits; source files in this directory supply the newly added implementation.

Follow that checkout's BUILDING.DEVCONTAINER.md and Windows release build script.
It requires the official custom LLVM/MinGW DWARF toolchain, Lua5.3.5, Boost,
SWIG and the original dependencies. A stock arbitrary MinGW build is not an
ABI-equivalent substitute. The build targets32-bit Windows FTL1.6.9.
Set POWERSHELL_TELEMETRY_OPTOUT=1, DOTNET_CLI_TELEMETRY_OPTOUT=1 and
VCPKG_DISABLE_METRICS=1 when provisioning dependencies; compile offline after
provisioning. This build uses the official devcontainer; dependency provisioning requires network access.
The exact upstream commit, toolchain image config digest and DLL SHA256 are in
BUILD_INFO.json. Do not overwrite the user's DLL without preserving their backup.

Portable checks (Linux): compile fleet_transport.cpp with tests/transport_test.cpp
using C++11 and pthread. tests/pixels_test.cpp is header-only. The Lua API test
uses Lua5.3.5 and stubs only video registration because FTL/OpenGL is unavailable.
It does NOT test native game ABI, graphics behavior or Windows sockets.

The scene path captures native drawing commands and replays local FTL assets.
FTL-specific capture/texture drawing needs a real Windows game test. The pure
pixel codec and transport are the parts covered by portable native tests.

For v0.26 also compile fleet_scene.cpp and fleet_effects.cpp (install_patch.py
adds these). C++11 is retained. Native combat API4 prevents v0.25 DLL reuse.
The scene codec test and effects application stub test are under tests/. The
stub test verifies mutation/validation logic, not native FTL struct layout.

For v0.28.9, also compile fleet_boarding.cpp (installer includes it).
Native effects API2 and boarding API1 are required for teleporter encounters.
Use tests/boarding_test.cpp with tests/effects_stubs for portable roster checks.

For v0.28.9, also compile fleet_boarding.cpp (installer includes it).
Native effects API2 and boarding API1 are required for teleporter encounters.
Use tests/boarding_test.cpp with tests/effects_stubs for portable roster checks.
