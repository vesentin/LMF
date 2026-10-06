"""
Thread-safe NRPPa encode/decode.

pycrate's NRPPA_PDU is a single shared object that stores the current value
inside itself, and it has no clone(). Encoding (set_val + to_aper) and decoding
(from_aper + read) are two steps on that object, so concurrent threads could mix
each other's values. A lock makes each encode/decode atomic.
"""
import copy
import threading

from pycrate_asn1dir import NRPPa

_lock = threading.Lock()


def encode(msg) -> bytes:
    """Encode an NRPPa PDU value (pycrate format) to APER bytes."""
    with _lock:
        M = NRPPa.NRPPA_PDU_Descriptions.NRPPA_PDU
        M.set_val(msg)
        return M.to_aper()


def decode(data: bytes):
    """Decode APER bytes to an independent copy of the NRPPa PDU value."""
    with _lock:
        M = NRPPa.NRPPA_PDU_Descriptions.NRPPA_PDU
        M.from_aper(data)
        return copy.deepcopy(M())
