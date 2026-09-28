# ULP 2.0.6 schema for the SUPL layer

## Why this exists

The SUPL/ULP schema that ships with Pycrate is OMA ULP 2.0.2 (July 2014). It has
no NR support: `PosMethod` has no NR methods, `CellInfo` has no NR cell, and the
SET capabilities cannot declare NR positioning. OMA ULP 2.0.6 (August 2020) adds
all of these (`ver2-NR-DL-TDOA`, `nrCell`, `additionalPositioningMethods`, ...).
Pycrate does not ship 2.0.6, but it does ship its ASN.1 compiler, so this folder
builds a Pycrate module from OMA's specification.

## Not stored in the repository

`src/ULP206.py` is generated from the ASN.1 text of OMA's specification, which is
published under the OMA Use Agreement
(https://www.openmobilealliance.org/about/policies/use-agreement/). That
agreement allows internal use but restricts copying, posting and modifying the
documents. Whether a generated schema may be published has not been clarified, so
the repository contains only the pipeline. Do not commit `src/ULP206.py`, the
extracted `.asn` files or the PDF (all are ignored by `.gitignore`).

## Requirements

bash, python3, `pdftotext` (package poppler-utils), git, wget or curl, network
access. Runtime: `pycrate` from pip (tested with 0.7.0).

## Usage

    tools/ulp206/make_ulp206.sh

Run it once after cloning and before `docker build`: `supl_message.py` imports
`ULP206`, and the Dockerfile copies `src/ULP206.py` into the image. Without the
file, `supl_message.py` stops with an error that points here.

## What it does

1. Downloads OMA-TS-ULP-V2_0_6-20200804-A.pdf and clones Pycrate (compiler and the
   ULP 2.0.2 baseline). Both go into `tools/ulp206/build/`.
2. `pdftotext -layout`, then `clean_ulp.py` cuts the 20 ASN.1 modules out of the
   text and drops the page headers and footers.
3. `make_compilable.py` removes comment lines that the PDF wrapped (they lost
   their `--`), splits braces glued to the next definition, and compares the
   result token by token with the 2.0.2 baseline.
4. Compiles with `pycrate_asn1compile.py`, runs `smoke206.py`, and only then
   copies the result to `src/ULP206.py`. Any failed check stops the run before
   anything is installed.
5. Writes `build/PROVENANCE.txt` (PDF hash, Pycrate commit, date).

## Checks

| Check | Expected | Meaning if it fails |
|---|---|---|
| PDF size | 4804666 bytes (warning only) | different revision of the document |
| modules in the PDF | 20 | extraction problem |
| hunks that delete baseline content | 0 | the cleaner is removing real code |
| hunks that replace baseline content | 4 | `aFLT`, `eCID`, `eOTD`, `oTDOA` renamed to lower case in 2.0.6 |
| module classes in `ULP206.py` | 20 | compile problem |
| `smoke206.py` | all pass | see below |

`smoke206.py` checks that a value present in both versions encodes to identical
bytes, that the legacy name `oTDOA` is rejected by 2.0.6, that
`ver2-NR-DL-TDOA` encodes to `0x0880` (extension index 8, as in the standard),
and that an NR cell and `AdditionalPositioningMethods` round-trip.

Known-good numbers for this revision: 83 wrapped comment lines removed.

## What differs between 2.0.2 and 2.0.6

Reviewed by hand in `build/make_report.txt`. Every difference is an addition apart
from the four renames:

- `PosMethod`: `ver2-mbs` and six NR methods (`ver2-NR-DL-TDOA` ... `ver2-NR-UL-AoA`)
- `nrCell` in `Ver2-CellInfo-extension`, with the `NRCellInformation` types
- `additionalPositioningMethods` (`nr-DL-TDOA`, ...) in the SET capabilities
- `nRAreaId`, `servingAMF` / `AMF-Identifier`, `nr` flags, 5G RSRP/RSRQ/SINR fields
- high-accuracy position, RTK, `ver2-imei`, `ver2-responseTime`, WLAN AP flags
- `%` allowed again in three URI character sets

## Limitations

- The ASN.1 comes from PDF text, and removing wrapped comments is a heuristic. The
  checks above catch dropped code, but the result has not been compared with any
  third-party SUPL implementation.
- The comparison is against 2.0.2 only, not against 2.0.3 to 2.0.5.

## Other revisions

Set `ULP_PDF_URL` (or `ULP_PDF`) and adjust `EXPECT_*`; then read
`build/diff_report.txt` and `build/make_report.txt` before trusting the result.

## Verified build

First run from scratch, 2026-09-28: PDF sha256
`707875de51f586373519f9185e59b0ae52653ecc5290a573698c1a112cc3049a` (4804666
bytes), Pycrate commit `82772f76c3feb22fd0257d4d0575f56dedd104b5`, Python 3.12.3,
20 modules, 83 wrapped comment lines removed. The result was byte-identical to
the module compiled by hand from the same PDF. Each run writes these values to
`build/PROVENANCE.txt` so a later run can be compared against them.
