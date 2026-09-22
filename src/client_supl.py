import socket
import random

from LPP_message_gen import generate_lpp_provide_assistance_data, generate_LPP_MESSAGE, generate_lpp_request_assistance_data
from LPP_handler import encodeLPP
from supl_message import (
    build_set_session_id,
    encode_supl_start,
    encode_supl_pos_init,
    encode_supl_end,
    recv_ulp_pdu,
    send_prs_payload_to_ue,
)

#SUPL server
HOST = "127.0.0.1"
PORT = 65001

#OAI side socket listener
UE_HOST = "127.0.0.1"
UE_PORT = 65000

transaction_id = random.randint(1, 200)

session_id_value = {'setSessionID': build_set_session_id(session_id=transaction_id, client_name='oai-ue-sim')}

body = generate_lpp_request_assistance_data('nr-DL-TDOA-RequestAssistanceData-r16')
full_msg = generate_LPP_MESSAGE(transaction_id, True, 0, lpp_message_body=body)
lpp_bytes = encodeLPP(full_msg)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
    client_sock.connect((HOST, PORT))

    state = 'START'
    while state != 'DONE':

        if state == 'START':
            request_pdu = encode_supl_start(session_id_value)
            client_sock.sendall(request_pdu)
            print(f"Sent SUPLSTART ({len(request_pdu)} bytes)")

            msg_type, msg_value, session_id_value = recv_ulp_pdu(client_sock)
            print(f"Received: {msg_type}")

            if msg_type == 'SUPLRESPONSE':
                state = 'POS_INIT'
            else:
                print(f"ERROR: expected SUPLRESPONSE, got {msg_type}. Aborting session.")
                state = 'DONE'

        elif state == 'POS_INIT':
            request_pdu = encode_supl_pos_init(session_id_value, lpp_bytes)
            client_sock.sendall(request_pdu)
            print(f"Sent SUPLPOSINIT ({len(request_pdu)} bytes)")

            msg_type, msg_value, session_id_value = recv_ulp_pdu(client_sock)
            print(f"Received: {msg_type}")

            if msg_type == 'SUPLPOS':
                response_lpp_bytes = msg_value['posPayLoad'][1]['lPPPayload'][0]
                print(f"Embedded LPP message: {len(response_lpp_bytes)} bytes")

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ue_sock:
                    ue_sock.connect((UE_HOST, UE_PORT))
                    send_prs_payload_to_ue(ue_sock, response_lpp_bytes)
                    print(f"Sent {len(response_lpp_bytes)}-byte full LPP message to UE")

                state = 'END'

        elif state == 'END':
            request_pdu = encode_supl_end(session_id_value)
            client_sock.sendall(request_pdu)
            print(f"Sent SUPLEND ({len(request_pdu)} bytes), session complete.")
            state = 'DONE'

print("Client finished.")
