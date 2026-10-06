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
_pending = {}                            # transaction ID -> set of gNB indices still expected
_cell_to_gnb = {}                        # (mcc, mnc, nr_cell_id) -> gNB index, set by the query
_stale = True                            # True = re-query on the next request
_next_txn = config.TRP_TXN_MIN


def new_transaction(expected_gnbs, cell_to_gnb: dict) -> int:
    """
    Pick a free transaction ID and record which gNBs are expected to answer it.
    cell_to_gnb maps (mcc, mnc, nr_cell_id) -> gNB index; it identifies the gNB
    behind each answer, since all answers to one request share its transaction ID.
    """
    global _next_txn
    with _cond:
        _cell_to_gnb.clear()
        _cell_to_gnb.update(cell_to_gnb)
        while _next_txn in _pending:
            _next_txn = _next_txn + 1 if _next_txn < config.TRP_TXN_MAX else config.TRP_TXN_MIN
        txn = _next_txn
        _next_txn = _next_txn + 1 if _next_txn < config.TRP_TXN_MAX else config.TRP_TXN_MIN
        _pending[txn] = set(expected_gnbs)
        return txn


def cancel_transaction(txn: int):
    """The request could not be sent: forget it and mark the table stale."""
    global _stale
    with _cond:
        _pending.pop(txn, None)
        _stale = True
        _cond.notify_all()


def is_table_transaction(txn: int) -> bool:
    """True if txn belongs to the TRP range (so the answer is for the table, not a UE session)."""
    return config.TRP_TXN_MIN <= txn <= config.TRP_TXN_MAX


def handle_response(txn: int, trp_list: list):
    """Store the TRPs of one TRP INFORMATION RESPONSE, identify the gNB by cell identity, wake the waiters."""
    global _stale
    with _cond:
        expected = _pending.get(txn)
        if expected is None:
            log.logger_NRPPa.warning(f"TRP table: response for unknown or expired transaction {txn}, ignored")
            return
        for item in trp_list:
            entry = parse_trp_information(item['tRPInformation'])
            entry.gnb_index = _cell_to_gnb.get((entry.mcc, entry.mnc, entry.nr_cell_id))
            if entry.gnb_index is None:
                log.logger_NRPPa.warning(
                    f"TRP table: TRP {entry.trp_id} has unknown cell identity "
                    f"({entry.mcc}, {entry.mnc}, {entry.nr_cell_id}); stored without gNB index")
            elif entry.gnb_index not in expected:
                log.logger_NRPPa.info(
                    f"TRP table: TRP {entry.trp_id} from gNB index {entry.gnb_index} was not expected "
                    f"(or already answered); stored anyway")
            expected.discard(entry.gnb_index)
            _entries[entry.trp_id] = entry
            log.logger_NRPPa.info(f"TRP table: stored TRP {entry.trp_id} from gNB index {entry.gnb_index}")
        if not expected:
            del _pending[txn]
        if not _pending:
            _stale = False
        _cond.notify_all()


def handle_failure(txn: int):
    """
    A TRP INFORMATION FAILURE. It carries no cell identity, so the failing gNB cannot be
    identified: mark the table stale and keep waiting for the other gNBs (the timeout ends the wait).
    """
    global _stale
    with _cond:
        _stale = True
        log.logger_NRPPa.warning(f"TRP table: TRP information failure for transaction {txn} "
                                 f"(failing gNB unknown); still waiting for the others")
        _cond.notify_all()


def wait_until_answered(txns: list, timeout: float) -> bool:
    """Block until all txns are complete (True), or the timeout expires (False)."""
    global _stale
    with _cond:
        done = _cond.wait_for(lambda: not any(t in _pending for t in txns), timeout)
        if not done:
            for t in txns:
                missing = _pending.pop(t, None)
                if missing:
                    log.logger_NRPPa.warning(f"TRP table: timeout on transaction {t}, "
                                             f"no answer from gNB indices {sorted(missing)}")
            _stale = True
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
