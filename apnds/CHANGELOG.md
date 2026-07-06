# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2026-06-10
### Fixed
* Remove forgotten debug print statement.

## [0.2.3] — 2026-05-30
### Added
* `__all__` fields to the source files which were missing them.
* Documentation and files related to PyPi release.

## [0.2.2] — 2026-05-30
### Fixed
* `Narc.to_bytes` now pads the filename table to a four-byte boundary.

## [0.2.1] — 2026-03-09
### Fixed
* The `CodeStartParams.get_sections` method now returns a mutable sequence of sections.
* The documentation of the `Overlay.compressed_size` field is fixed.

## [0.2.0] — 2026-03-06
### Added
* Added DSi header fields (and automatically setting some of them).
* The ARM9i and ARM7i are now parsed when reading and added when exporting.
* The modcrypt areas in DSi ROMs are now decrypted.
* The modified backwards LZ compression algorithm used for code has been implemented.
* Parsing the start parameters structure and modifying it has been implemented.
* Unpacking the code in terms of automatically loaded sections, and repacking,
with added or removed or modified sections, has been implemented.

## [0.1.2] — 2025-12-30
### Fixed
* The feature implemented in the previous version now works correctly.

## [0.1.1] — 2025-12-30
### Changed
* Files that were added to `Rom.files` but not to `Rom.file_order`
are automatically appended to the end of the file order before the Rom is reconstructed.

## [0.1.0] — 2025-12-30
The first release of this project.

[0.2.4]: https://github.com/ljtpetersen/apnds/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/ljtpetersen/apnds/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/ljtpetersen/apnds/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/ljtpetersen/apnds/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/ljtpetersen/apnds/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/ljtpetersen/apnds/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/ljtpetersen/apnds/compare/v0.1...v0.1.0
[0.1.0]: https://github.com/ljtpetersen/apnds/releases/tag/v0.1
