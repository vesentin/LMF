#!/usr/bin/env bash
#
# Regenerates src/ULP206.py: the OMA ULP 2.0.6 schema, compiled for Pycrate.
# See README.md in this directory for the why and the details.
#
# Nothing derived from OMA's specification is stored in the repository: this
# script downloads the specification from OMA and builds the module locally.
#
# Environment overrides (all optional):
#   ULP_PDF        use this local PDF instead of downloading one
#   ULP_PDF_URL    download location of the PDF
#   PYCRATE_DIR    use an existing Pycrate checkout (default: clone into build/)
#   PYCRATE_REF    branch or tag to clone (default: master)
#   BUILD_DIR      working directory (default: tools/ulp206/build)
#   PDFTOTEXT      pdftotext binary
#   EXPECT_MODULES / EXPECT_REPLACES / EXPECT_PDF_SIZE   sanity-check values
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$HERE/../../src" && pwd)"
BUILD="${BUILD_DIR:-$HERE/build}"
PDF_URL="${ULP_PDF_URL:-https://www.openmobilealliance.org/release/SUPL/V2_0_6-20200804-A/OMA-TS-ULP-V2_0_6-20200804-A.pdf}"
PDF="${ULP_PDF:-$BUILD/OMA-TS-ULP-V2_0_6-20200804-A.pdf}"
PYCRATE_DIR="${PYCRATE_DIR:-$BUILD/pycrate}"
PYCRATE_REF="${PYCRATE_REF:-master}"
PDFTOTEXT="${PDFTOTEXT:-pdftotext}"
EXPECT_MODULES="${EXPECT_MODULES:-20}"
EXPECT_REPLACES="${EXPECT_REPLACES:-4}"
EXPECT_PDF_SIZE="${EXPECT_PDF_SIZE:-4804666}"

die()  { echo "ERROR: $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }
count() { grep -c "$1" "$2" || true; }

step "checking tools"
command -v python3 >/dev/null   || die "python3 not found"
command -v "$PDFTOTEXT" >/dev/null || die "pdftotext not found (package poppler-utils)"
mkdir -p "$BUILD"

step "specification PDF"
if [ ! -s "$PDF" ]; then
    echo "downloading $PDF_URL"
    if   command -v wget >/dev/null; then wget -q -O "$PDF" "$PDF_URL"
    elif command -v curl >/dev/null; then curl -sSL -o "$PDF" "$PDF_URL"
    else die "neither wget nor curl found"; fi
fi
[ -s "$PDF" ] || die "PDF missing or empty: $PDF"
PDF_SIZE="$(stat -c %s "$PDF")"
echo "$PDF: $PDF_SIZE bytes"
if [ "$PDF_SIZE" != "$EXPECT_PDF_SIZE" ]; then
    echo "WARNING: expected $EXPECT_PDF_SIZE bytes; this may not be the revision the checks were written for" >&2
fi

step "Pycrate (compiler + ULP 2.0.2 baseline)"
if [ ! -d "$PYCRATE_DIR" ]; then
    command -v git >/dev/null || die "git not found"
    git clone --depth 1 --branch "$PYCRATE_REF" https://github.com/pycrate-org/pycrate.git "$PYCRATE_DIR"
fi
PYCRATE_DIR="$(cd "$PYCRATE_DIR" && pwd)"
BASELINE="$PYCRATE_DIR/pycrate_asn1dir/OMA_ULP"
[ -d "$BASELINE" ] || die "baseline schema not found: $BASELINE"
[ -f "$PYCRATE_DIR/tools/pycrate_asn1compile.py" ] || die "compiler not found in $PYCRATE_DIR/tools"

step "extracting the ASN.1 modules from the PDF"
"$PDFTOTEXT" -layout "$PDF" "$BUILD/ulp.txt"
rm -rf "$BUILD/pdf_modules" "$BUILD/pdf206"
python3 "$HERE/clean_ulp.py" "$BUILD/ulp.txt" "$BASELINE" "$BUILD/pdf_modules" > "$BUILD/diff_report.txt"
N_MODULES="$(ls "$BUILD"/pdf_modules/*.asn 2>/dev/null | wc -l)"
echo "modules found in the PDF: $N_MODULES"
[ "$N_MODULES" = "$EXPECT_MODULES" ] || die "expected $EXPECT_MODULES modules, found $N_MODULES"

step "removing wrapped comments and verifying against the 2.0.2 baseline"
python3 "$HERE/make_compilable.py" "$BUILD/pdf_modules" "$BASELINE" "$BUILD/pdf206" > "$BUILD/make_report.txt"
N_DELETES="$(count '\[delete\]' "$BUILD/make_report.txt")"
N_REPLACES="$(count '\[replace\]' "$BUILD/make_report.txt")"
echo "$(tail -1 "$BUILD/make_report.txt")"
echo "hunks that delete baseline content: $N_DELETES (expected 0)"
echo "hunks that replace baseline content: $N_REPLACES (expected $EXPECT_REPLACES: the renamed PosMethod identifiers)"
[ "$N_DELETES" = "0" ] || die "the cleaner is dropping real code, see $BUILD/make_report.txt"
[ "$N_REPLACES" = "$EXPECT_REPLACES" ] || die "unexpected number of replaced definitions, see $BUILD/make_report.txt"

step "compiling with Pycrate's ASN.1 compiler"
( cd "$BUILD" && rm -f ULP206.py \
  && PYTHONPATH="$PYCRATE_DIR" python3 "$PYCRATE_DIR/tools/pycrate_asn1compile.py" -i pdf206/*.asn -o ULP206 )
[ -s "$BUILD/ULP206.py" ] || die "the compiler produced no output"
N_CLASSES="$(count '^class ' "$BUILD/ULP206.py")"
echo "ULP206.py: $(stat -c %s "$BUILD/ULP206.py") bytes, $N_CLASSES module classes"
[ "$N_CLASSES" = "$EXPECT_MODULES" ] || die "expected $EXPECT_MODULES module classes, found $N_CLASSES"

step "self-check of the compiled module"
( cd "$BUILD" && EXPECT_MODULES="$EXPECT_MODULES" PYTHONPATH="$PYCRATE_DIR:$BUILD" python3 "$HERE/smoke206.py" )

step "installing"
cp "$BUILD/ULP206.py" "$SRC_DIR/ULP206.py"
{
    echo "generated:      $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "pdf url:        $PDF_URL"
    echo "pdf size:       $PDF_SIZE"
    echo "pdf sha256:     $(sha256sum "$PDF" | cut -d' ' -f1)"
    echo "pycrate commit: $(git -C "$PYCRATE_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "python:         $(python3 --version 2>&1)"
    echo "modules:        $N_MODULES"
    echo "cleaner:        $(tail -1 "$BUILD/make_report.txt")"
} > "$BUILD/PROVENANCE.txt"
echo "wrote $SRC_DIR/ULP206.py (provenance: $BUILD/PROVENANCE.txt)"
echo
echo "Done. src/ULP206.py is derived from OMA's specification: do not commit it (see README.md)."
