#!/usr/bin/env python3
"""
Self-check for a freshly compiled ULP module (ULP206.py) against the ULP 2.0.2
schema that ships with Pycrate. Exits non-zero if any check fails.
"""
import os, sys
from pycrate_asn1dir import ULP as OLD      # ULP 2.0.2, shipped with Pycrate
import ULP206 as NEW                        # ULP 2.0.6, compiled from the OMA PDF

EXPECT_MODULES = int(os.environ.get('EXPECT_MODULES', '20'))
failures = []

def step(title, fn):
    try:
        print(f'[ok]   {title}: {fn()}')
    except Exception as e:
        failures.append(title)
        print(f'[FAIL] {title}: {type(e).__name__}: {str(e)[:300]}')

def resp(mod, value):
    o = mod.SUPL_RESPONSE.SUPLRESPONSE
    o.set_val(value)
    return o.to_uper()

def modules():
    names = sorted(n for n in dir(NEW) if n.startswith(('SUPL', 'ULP', 'Ver2')))
    assert len(names) == EXPECT_MODULES, f'{len(names)} module classes, expected {EXPECT_MODULES}'
    return f'{len(names)} module classes'

def regression():
    # a value that exists in both versions must encode to identical bytes
    a, b = resp(OLD, {'posMethod': 'oTDOA'}), resp(NEW, {'posMethod': 'otdoa'})
    assert a == b, f'encodings differ: old={a.hex()} new={b.hex()}'
    return f'identical ({a.hex()})'

def old_name():
    # 2.0.6 renamed the legacy identifiers to lower case
    try:
        resp(NEW, {'posMethod': 'oTDOA'})
    except Exception as e:
        return f'rejected as expected ({type(e).__name__})'
    raise AssertionError("'oTDOA' is still accepted")

def nr_method():
    b = resp(NEW, {'posMethod': 'ver2-NR-DL-TDOA'})
    # 4 preamble bits, extension flag, extension index 8 -> 0x0880. A different
    # value means the extension additions are no longer in the standard's order.
    assert b.hex() == '0880', f'unexpected encoding {b.hex()}'
    o = NEW.SUPL_RESPONSE.SUPLRESPONSE
    o.from_uper(b)
    assert o.get_val() == {'posMethod': 'ver2-NR-DL-TDOA'}, o.get_val()
    return b.hex()

def nr_cell():
    value = {'cellInfo': ('ver2-CellInfo-extension', ('nrCell', {
        'servingCellInformation': [{
            'physCellId': 0,
            'arfcn-NR': 497770,
            'cellGlobalId': {'plmn-Identity': {'mcc': [2, 0, 8], 'mnc': [9, 5]},
                             'cellIdentityNR': (12345678, 36)},
            'trackingAreaCode': (0xA000, 24)}]})),
        'status': 'current'}
    loc = NEW.ULP_Components.LocationId
    loc.set_val(value)
    b = loc.to_uper()
    loc.from_uper(b)
    assert loc.get_val() == value, loc.get_val()
    return f'{len(b)} bytes, round trip identical'

def addpos():
    value = [{'addPosID': 'nr-DL-TDOA', 'addPosMode': (0b001, 3)}]
    o = NEW.ULP_Version_2_parameter_extensions.AdditionalPositioningMethods
    o.set_val(value)
    b = o.to_uper()
    o.from_uper(b)
    assert o.get_val() == value, o.get_val()
    return f'{len(b)} bytes, round trip identical'

step('module classes', modules)
step('regression: SUPLRESPONSE oTDOA (2.0.2) == otdoa (2.0.6)', regression)
step("legacy name 'oTDOA' rejected by 2.0.6", old_name)
step('SUPLRESPONSE ver2-NR-DL-TDOA: encoding + round trip', nr_method)
step('LocationId with nrCell: round trip', nr_cell)
step('AdditionalPositioningMethods nr-DL-TDOA: round trip', addpos)

if failures:
    print(f'\n{len(failures)} check(s) FAILED: {failures}')
    sys.exit(1)
print('\nall checks passed')
