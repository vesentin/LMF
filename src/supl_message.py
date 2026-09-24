"""
Helper functions for building and encoding minimal SUPL/ULP messages,
using Pycrate's ULP ASN.1 module.

Each function returns a ready-to-encode Pycrate value; call .set_val(...) on the
corresponding Pycrate type object, then .to_uper() to get real bytes.

Reference: pycrate_asn1dir/ULP.py (OMA ULP / SUPL ASN.1 definitions)
"""

from pycrate_asn1dir import ULP


# ---------------------------------------------------------------------
# Shared building blocks (reused across multiple message types)
# ---------------------------------------------------------------------

def build_default_set_capabilities():
    """
    Builds a minimal, dummy SETCapabilities value (SUPL-START.SETCapabilities).
    Mandatory fields: posTechnology, prefMethod, posProtocol.

    PERMANENT LIMITATION, not a TODO: posTechnology's available flags
    (agpsSETassisted, agpsSETBased, autonomousGPS, aflt, ecid, eotd, otdoa)
    are all legacy 2G/3G/A-GNSS technologies -- this ULP schema version has
    no NR/5G-specific capability flag at all, so no value here can
    correctly represent this project's actual UE capabilities. otdoa=True
    is used as the closest available legacy analogue, not a real claim.
    """
    return {
        'posTechnology': {
            'agpsSETassisted': False,
            'agpsSETBased': False,
            'autonomousGPS': False,
            'aflt': False,
            'ecid': False,
            'eotd': False,
            'otdoa': True,
        },
        'prefMethod': 'noPreference',
        'posProtocol': {
            'tia801': False,
            'rrlp': False,
            'rrc': True,
        },
    }


def build_default_location_id():
    """
    Builds a minimal, dummy LocationId value (ULP-Components.LocationId).
    Mandatory fields: cellInfo, status.
  
    PERMANENT LIMITATION, not a TODO: the base CellInfo CHOICE (and its
    version-2 extension, checked directly in this schema) has no NR/5G
    cell-identification option -- only legacy 2G/3G formats (gsmCell,
    wcdmaCell, etc.) exist. A dummy gsmCell value is used since there is
    no schema-valid way to represent a real NR cell here.
    """
    return {
        'cellInfo': ('gsmCell', {
            'refMCC': 1,
            'refMNC': 1,
            'refLAC': 1,
            'refCI': 1,
        }),
        'status': 'current',
    }


def build_supl_pos_with_lpp(lpp_message_bytes):
    """
    Builds a SUPLPOS value (SUPL-POS.SUPLPOS) carrying a single LPP message.

    lpp_message_bytes: raw UPER-encoded LPP message bytes, e.g. produced by
    LPP_handler.encodeLPP() on the LMF side, or by OAI's uper_encode_to_buffer
    on the UE side.

    Note: lPPPayload is a SEQUENCE OF (list) of 1-3 LPP messages; this
    function always wraps exactly one message per SUPLPOS, for simplicity.
    NR/5G LPP support requires the ver2-PosPayLoad-extension, since no
    lPPPayload option exists at the base PosPayLoad CHOICE level.
    """
    return {
        'posPayLoad': ('ver2-PosPayLoad-extension', {
            'lPPPayload': [lpp_message_bytes],
        }),
    }


# ---------------------------------------------------------------------
# Top-level SUPL message builders
# ---------------------------------------------------------------------

def build_supl_start():
    """
    Builds a minimal SUPLSTART value (SUPL-START.SUPLSTART).
    Mandatory fields: sETCapabilities, locationId.
    Optional fields omitted: qoP, ver2-SUPL-START-extension.
    """
    return {
        'sETCapabilities': build_default_set_capabilities(),
        'locationId': build_default_location_id(),
    }


def build_supl_pos_init(lpp_message_bytes):
    """
    Builds a minimal SUPLPOSINIT value (SUPL-POS-INIT.SUPLPOSINIT), which
    both initiates a SUPL session and carries a first LPP message, embedded
    via the optional 'suplpos' field (a full nested SUPLPOS structure).

    Mandatory fields: sETCapabilities, locationId.
    Optional fields used: suplpos (carrying the LPP payload).
    Optional fields omitted: requestedAssistData (GNSS-specific, not
    relevant to NR DL-TDoA), position, ver, version-2 extension.
    """
    return {
        'sETCapabilities': build_default_set_capabilities(),
        'locationId': build_default_location_id(),
        'suplpos': build_supl_pos_with_lpp(lpp_message_bytes),
    }


def build_supl_response(pos_method='oTDOA'):
    """
    Builds a minimal SUPLRESPONSE value (SUPL-RESPONSE.SUPLRESPONSE).
    Mandatory field: posMethod.

    PERMANENT LIMITATION, not a TODO: this ULP schema version's posMethod
    ENUM has no NR/5G-specific value, in the base type or its version-2
    extensions. 'oTDOA' is used as the closest legacy analogue. This is
    session-level metadata only -- it does not affect the actual LPP
    payload content carried separately in SUPLPOS.
    """
    return {
        'posMethod': pos_method,
    }


def build_supl_end():
    """
    Builds a minimal, empty SUPLEND value (SUPL-END.SUPLEND).
    All fields (position, statusCode, ver, extension) are optional;
    an empty session-close message is protocol-valid.
    """
    return {}


# ---------------------------------------------------------------------
# ULP_PDU envelope: the REAL top-level structure sent over the wire.
# Every SUPL message (SUPLSTART, SUPLPOSINIT, SUPLPOS, ...) built above
# is only the *content* of this envelope's 'message' CHOICE field.
# ---------------------------------------------------------------------

# Message-type CHOICE names, as defined in ULP.UlpMessage._cont.
# Maps a short, convenient name to the exact ASN.1 CHOICE option name.
ULP_MESSAGE_TYPES = {
    'SUPLSTART': 'msSUPLSTART',
    'SUPLRESPONSE': 'msSUPLRESPONSE',
    'SUPLPOSINIT': 'msSUPLPOSINIT',
    'SUPLPOS': 'msSUPLPOS',
    'SUPLEND': 'msSUPLEND',
}


def build_default_version():
    """
    Builds a minimal Version value (ULP-Components.Version).
    All three fields mandatory: maj, min, servind (protocol version numbers).
    Using 2/0/0 as a placeholder for "SUPL 2.0".
    """
    return {'maj': 2, 'min': 0, 'servind': 0}


def build_set_session_id(session_id, client_name='None'):
    """
    Builds a SetSessionID value (ULP-Components.SetSessionID).
    Identifies the client side of a session.

    session_id: integer, 0-65535, picked by the client for this session.
    client_name: string used as the 'nai' (Network Access Identifier)
    SETId CHOICE option -- the simplest of the available SETId options
    (msisdn/mdn/min/imsi/nai/iPAddress) to fill without a real subscriber
    identity. If not given, defaults to a string derived from session_id
    so distinct sessions are at least distinguishable in logs -- this is
    still a placeholder identity, not a real one; no SETId option here
    can currently be populated with genuine subscriber data.
    """
    if client_name is None:
        client_name = f"ue-session-{session_id}"

    return {
        'sessionId': session_id,
        'setId': ('nai', client_name),
    }

def build_slp_session_id(session_id_bytes, ip_bytes=b'\x7f\x00\x00\x01'):
    """
    Builds an SlpSessionID value (ULP-Components.SlpSessionID).
    Identifies the server side of a session, once established.

    session_id_bytes: exactly 4 raw bytes (fixed size per schema constraint),
    chosen by the server as a session identifier.
    ip_bytes: 4 raw bytes representing the server's IPv4 address; defaults
    to 127.0.0.1 (loopback). In practice this should be overridden with
    the LMF's real deployment address (see config.LMF_PUBLIC_IP), since
    loopback is only correct when client and server run on the same host.
    """
    return {
        'sessionID': session_id_bytes,
        'slpId': ('iPAddress', ('ipv4Address', ip_bytes)),
    }

def _encode_ulp_pdu(session_id_value, message_type_name, message_value):
    """
    Internal helper: encodes a full ULP_PDU given a session ID value,
    a message type (one of ULP_MESSAGE_TYPES' keys), and that message's
    content value.

    Handles the two-pass 'length' field encoding: encodes once with a
    placeholder length, measures the real byte count, then re-encodes
    with the correct length. This works because 'length' is a constrained
    integer (0-65535) and therefore always occupies the same number of
    bits in UPER regardless of its value.
    """
    if message_type_name not in ULP_MESSAGE_TYPES:
        raise ValueError(f"Unknown message type: {message_type_name}")

    choice_name = ULP_MESSAGE_TYPES[message_type_name]
    pdu_type = ULP.ULP.ULP_PDU

    # First pass: placeholder length = 0
    pdu_value = {
        'length': 0,
        'version': build_default_version(),
        'sessionID': session_id_value,
        'message': (choice_name, message_value),
    }
    pdu_type.set_val(pdu_value)
    real_length = len(pdu_type.to_uper())

    # Second pass: real length
    pdu_value['length'] = real_length
    pdu_type.set_val(pdu_value)
    encoded = pdu_type.to_uper()

    assert len(encoded) == real_length, (
        "Encoded length changed between passes -- length field may not be "
        "a fixed-width constrained integer as assumed."
    )
    return encoded


def decode_ulp_pdu(data):
    """
    Decodes raw bytes as a ULP_PDU and returns (message_type_name,
    message_value, session_id_value), using the short names from
    ULP_MESSAGE_TYPES rather than the raw ASN.1 CHOICE option names.

    """
    pdu_type = ULP.ULP.ULP_PDU
    pdu_type.from_uper(data)
    decoded = pdu_type.get_val()

    choice_name, message_value = decoded['message']
    reverse_lookup = {v: k for k, v in ULP_MESSAGE_TYPES.items()}
    message_type_name = reverse_lookup.get(choice_name, choice_name)

    return message_type_name, message_value, decoded['sessionID']

def recv_ulp_pdu(sock, max_buffer_size=65536):
    """
    Accumulates bytes from sock until a complete ULP_PDU can be decoded.
    UPER is not byte aligned, so we cannot know the message is complete from 
    its length, we rety decoding every new chunk instead.

    max_buffer_size guards against buffering forever on a stream that will never decode
    (e.g. corrupted data).
    """
    buffer = b''
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Socket closed before a full message was received")
        buffer += chunk
       
        if len(buffer) > max_buffer_size:
            raise ValueError(
                f"ULP_PDU exceeded {max_buffer_size} bytes without decoding "
                f"successfully --likely malformed or wrong protocol data"
            )

        try:
            msg_type, msg_value, session_id_value = decode_ulp_pdu(buffer)
            return msg_type, msg_value, session_id_value
        except Exception:
            # Not enough bytes yet to decode a complete message -- keep reading.
            continue

# ---------------------------------------------------------------------
# Top-level encode helpers: build a message's content AND wrap it in a
# ULP_PDU envelope in one call.
# ---------------------------------------------------------------------

def encode_supl_pos_init(session_id_value, lpp_message_bytes):
    message_value = build_supl_pos_init(lpp_message_bytes)
    return _encode_ulp_pdu(session_id_value, 'SUPLPOSINIT', message_value)


def encode_supl_pos(session_id_value, lpp_message_bytes):
    message_value = build_supl_pos_with_lpp(lpp_message_bytes)
    return _encode_ulp_pdu(session_id_value, 'SUPLPOS', message_value)


def encode_supl_start(session_id_value):
    message_value = build_supl_start()
    return _encode_ulp_pdu(session_id_value, 'SUPLSTART', message_value)


def encode_supl_response(session_id_value, pos_method='oTDOA'):
    message_value = build_supl_response(pos_method)
    return _encode_ulp_pdu(session_id_value, 'SUPLRESPONSE', message_value)


def encode_supl_end(session_id_value):
    message_value = build_supl_end()
    return _encode_ulp_pdu(session_id_value, 'SUPLEND', message_value)

import struct

def send_prs_payload_to_ue(sock, ue_payload_bytes):
    """
    Frame and send raw UPER NR-DL-PRS-AssistanceData-r16 bytes to the
    OAI UE's SUPL socket listener. Minimal header: 4-byte big-endian
    payload length, no magic/version/type yet -- see supl_socket.c.
    """
    header = struct.pack('>I', len(ue_payload_bytes))
    sock.sendall(header + ue_payload_bytes)

# ---------------------------------------------------------------------
# Quick self-test: build, encode, and round-trip-verify every message
# ---------------------------------------------------------------------

if __name__ == '__main__':
    from LPP_message_gen import generate_lpp_request_assistance_data, generate_LPP_MESSAGE
    from LPP_handler import encodeLPP

    body = generate_lpp_request_assistance_data('nr-DL-TDOA-RequestAssistanceData-r16')
    full_msg = generate_LPP_MESSAGE(1, True, 0, lpp_message_body=body)
    lpp_bytes = encodeLPP(full_msg)
    print(f"LPP bytes: {len(lpp_bytes)}")

    # SUPL START
    t = ULP.SUPL_START.SUPLSTART
    t.set_val(build_supl_start())
    enc = t.to_uper()
    print(f"SUPLSTART: {len(enc)} bytes")

    # SUPL POS INIT (with embedded LPP-carrying SUPLPOS)
    t = ULP.SUPL_POS_INIT.SUPLPOSINIT
    t.set_val(build_supl_pos_init(lpp_bytes))
    enc = t.to_uper()
    t.from_uper(enc)
    decoded = t.get_val()
    recovered = decoded['suplpos']['posPayLoad'][1]['lPPPayload'][0]
    print(f"SUPLPOSINIT: {len(enc)} bytes, LPP round-trip OK: {recovered == lpp_bytes}")

    # SUPL POS (standalone)
    t = ULP.SUPL_POS.SUPLPOS
    t.set_val(build_supl_pos_with_lpp(lpp_bytes))
    enc = t.to_uper()
    print(f"SUPLPOS: {len(enc)} bytes")

    # SUPL RESPONSE
    t = ULP.SUPL_RESPONSE.SUPLRESPONSE
    t.set_val(build_supl_response())
    enc = t.to_uper()
    print(f"SUPLRESPONSE: {len(enc)} bytes")

    # SUPL END
    t = ULP.SUPL_END.SUPLEND
    t.set_val(build_supl_end())
    enc = t.to_uper()
    print(f"SUPLEND: {len(enc)} bytes")

    print("All SUPL message builders validated successfully.")

    # --- ULP_PDU envelope test ---
    session_id_value = {'setSessionID': build_set_session_id(1, 'test-client')}
    wrapped = encode_supl_pos_init(session_id_value, lpp_bytes)
    print(f"\nULP_PDU-wrapped SUPLPOSINIT: {len(wrapped)} bytes")

    msg_type, msg_value, decoded_session_id = decode_ulp_pdu(wrapped)
    print(f"Decoded message type: {msg_type}")
    recovered = msg_value['suplpos']['posPayLoad'][1]['lPPPayload'][0]
    print(f"LPP round-trip through ULP_PDU OK: {recovered == lpp_bytes}")
    print(f"Session ID recovered: {decoded_session_id}")
