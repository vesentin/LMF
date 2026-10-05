"""
Network-level table of TRP information, filled from NRPPa TRP Information
Exchange (TS 38.455 sec. 8.2.8) and shared by all positioning sessions.

The entry type and the parser for one decoded TRPInformation.
"""
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Optional

import config
import custom_log as log


@dataclass
class TrpEntry:
    trp_id: int
    gnb_index: Optional[int] = None      # which queried gNB answered (from the request's transaction ID)
    pci: Optional[int] = None
    mcc: Optional[str] = None
    mnc: Optional[str] = None
    nr_cell_id: Optional[int] = None
    arfcn: Optional[int] = None
    position: Optional[dict] = None      # simplified geographicalCoordinates
    prs: Optional[dict] = None           # reserved for the PRS configuration
    updated: float = field(default_factory=time.time)


def _plmn_from_tbcd(plmn: bytes):
    """Decode a 3-byte TBCD PLMN identity into (mcc, mnc) digit strings."""
    d = [plmn[0] & 0x0F, plmn[0] >> 4,
         plmn[1] & 0x0F, plmn[1] >> 4,
         plmn[2] & 0x0F, plmn[2] >> 4]
    mcc = f"{d[0]}{d[1]}{d[2]}"
    if d[3] == 0xF:                      # 2-digit MNC: third digit is the filler F
        mnc = f"{d[4]}{d[5]}"
    else:
        mnc = f"{d[4]}{d[5]}{d[3]}"
    return mcc, mnc


def _parse_position(geo: dict) -> dict:
    """Simplify geographicalCoordinates; keep the raw value for formats not handled yet."""
    kind, value = geo['tRPPositionDefinitionType']
    if kind == 'referenced':
        ref_type, ref_val = value['referencePointType']
        if ref_type == 'tRPPositionRelativeCartesian':
            return {
                'reference': value['referencePoint'],
                'unit': ref_val['xYZunit'],
                'x': ref_val['xvalue'],
                'y': ref_val['yvalue'],
                'z': ref_val['zvalue'],
            }
    return {'raw': geo}


def parse_trp_information(trp_info: dict, gnb_index: Optional[int] = None) -> TrpEntry:
    """Turn one decoded TRPInformation (pycrate dict) into a TrpEntry."""
    entry = TrpEntry(trp_id=trp_info['tRP-ID'], gnb_index=gnb_index)
    for kind, value in trp_info['tRPInformationTypeResponseList']:
        if kind == 'pCI-NR':
            entry.pci = value
        elif kind == 'cGI-NR':
            entry.mcc, entry.mnc = _plmn_from_tbcd(value['pLMN-Identity'])
            entry.nr_cell_id = value['nRcellIdentifier'][0]
        elif kind == 'aRFCN':
            entry.arfcn = value
        elif kind == 'geographicalCoordinates':
            entry.position = _parse_position(value)
        elif kind == 'pRSConfiguration':
            entry.prs = value            # stored raw until the PRS work defines its format
        else:
            log.logger_NRPPa.warning(f"TRP {entry.trp_id}: unhandled TRP information type '{kind}'")
    return entry

_cond = threading.Condition()            # a lock plus wait/notify
_entries = {}                            # trp_id -> TrpEntry
_pending = {}                            # transaction ID -> gnb_index (requests not answered yet)
_stale = True                            # True = re-query on the next request
_next_txn = config.TRP_TXN_MIN


def new_transaction(gnb_index: int) -> int:
    """Pick a free transaction ID from the TRP range and record it as pending."""
    global _next_txn
    with _cond:
        while _next_txn in _pending:
            _next_txn = _next_txn + 1 if _next_txn < config.TRP_TXN_MAX else config.TRP_TXN_MIN
        txn = _next_txn
        _next_txn = _next_txn + 1 if _next_txn < config.TRP_TXN_MAX else config.TRP_TXN_MIN
        _pending[txn] = gnb_index
        return txn


def is_table_transaction(txn: int) -> bool:
    """True if txn belongs to the TRP range (so the answer is for the table, not a UE session)."""
    return config.TRP_TXN_MIN <= txn <= config.TRP_TXN_MAX


def handle_response(txn: int, trp_list: list):
    """Store the TRPs of one TRP INFORMATION RESPONSE and wake the waiters."""
    global _stale
    with _cond:
        gnb_index = _pending.pop(txn, None)
        if gnb_index is None:
            log.logger_NRPPa.warning(f"TRP table: response for unknown or expired transaction {txn}, ignored")
            return
        for item in trp_list:
            entry = parse_trp_information(item['tRPInformation'], gnb_index)
            _entries[entry.trp_id] = entry
            log.logger_NRPPa.info(f"TRP table: stored TRP {entry.trp_id} from gNB index {gnb_index}")
        if not _pending:
            _stale = False
        _cond.notify_all()


def handle_failure(txn: int):
    """A TRP INFORMATION FAILURE: forget the request, mark the table stale, wake the waiters."""
    global _stale
    with _cond:
        gnb_index = _pending.pop(txn, None)
        _stale = True
        log.logger_NRPPa.warning(f"TRP table: TRP information failure for transaction {txn} (gNB index {gnb_index})")
        _cond.notify_all()


def wait_until_answered(txns: list, timeout: float) -> bool:
    """Block until all txns are answered (True), or the timeout expires (False)."""
    global _stale
    with _cond:
        done = _cond.wait_for(lambda: not any(t in _pending for t in txns), timeout)
        if not done:
            for t in txns:
                _pending.pop(t, None)        # a late answer will now be ignored
            _stale = True
            log.logger_NRPPa.warning(f"TRP table: timeout waiting for transactions {txns}")
        return done


def is_fresh() -> bool:
    """True if the table has entries, no failure/timeout since, and is younger than the max age."""
    with _cond:
        if _stale or not _entries:
            return False
        oldest = min(e.updated for e in _entries.values())
        return time.time() - oldest < config.TRP_TABLE_MAX_AGE_S


def snapshot() -> list:
    """A copy of the current entries, safe to use without holding the lock."""
    with _cond:
        return [replace(e) for e in _entries.values()]

def handle_nrppa_answer(message_type: str, body: dict):
    """Route a decoded TRP Information Exchange answer (response or failure) to the table."""
    txn = body['nrppatransactionID']
    if message_type == 'successfulOutcome':
        for ie in body['value'][1]['protocolIEs']:
            if ie['value'][0] == 'TRPInformationListTRPResp':
                handle_response(txn, ie['value'][1])
                return
        log.logger_NRPPa.warning(f"TRP table: response {txn} without a TRP information list")
    handle_failure(txn)
