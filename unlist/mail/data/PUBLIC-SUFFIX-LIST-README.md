# Public Suffix List

`public_suffix_list.dat` is the Public Suffix List, shipped **unmodified**, byte for byte, with its MPL header.

- Source: <https://publicsuffix.org/list/public_suffix_list.dat> (this copy taken from <https://github.com/publicsuffix/list>)
- Commit: `88b076a1fb2ae58cd2a6959d570f075e04d21867`
- Snapshot date: 2026-11-26
- Licence: Mozilla Public License 2.0 (<https://mozilla.org/MPL/2.0/>). The licence text is in `LICENSE.MPL-2.0` next to it. The source of this file is the file itself.
- Updates: only with a release of Unlist. There is no runtime refresh.

`public-suffix-list.json` records the SHA-256 of the file. A test in `unlist/legal/tests/` fails if the file changes without the digest, so an accidental edit (an editor changing line endings, for example) is caught. When updating the list, replace the file with the new upstream copy and update the digest, commit and date here and in `THIRD-PARTY-NOTICES`.
