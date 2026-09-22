# LMF — SUPL Transport for NR DL-TDoA

## Setup notes

### PRS configuration file

`docker-compose-lmf.yaml` mounts a PRS configuration file into the container
at `/LMF/prs.conf`, read by the LMF to generate real NR-DL-PRS-AssistanceData-r16
content. This currently points at:

    ue.nr.prs.fr1.106prb.conf

from the EURECOM OAI test setup (targets/PROJECTS/GENERIC-NR-5GC/CONF/), and is
NOT included in this repository. Before running, set OAI_CONF_DIR to the
directory containing this file on your own machine, e.g.:

    export OAI_CONF_DIR=/path/to/openairinterface5g/targets/PROJECTS/GENERIC-NR-5GC/CONF

Note: only gNB_id 0 and 1 in this config currently have corresponding real
OAI gNB .conf files (physCellId, ARFCN); prs_config2/prs_config3 exist in the
file but are not currently used.

### Network configuration (src/config.py)

`AMF_IP` and `CN_Used` in `config.py` are set to match the EURECOM test
network and will likely need to be changed for a different environment.
`LMF_IP = '0.0.0.0'` is intentional (binds all interfaces, works both inside
Docker and bare-metal) and should not need to change.

### SUPL ports

- LMF SUPL listener: port 65001 (integrated into lmf_server_api.py)
- OAI UE SUPL listener: port 65000

## New/modified files (SUPL transport work)

- `src/supl_message.py` — SUPL/ULP message building, encoding, and ULP_PDU
  framing (new)
- `src/client_supl.py` — Python SUPL client; completes a SUPL session against
  the LMF and forwards the LPP message to the OAI
  UE over a socket (new)
- `src/prs_config.py` — parses OAI's PRS .conf file format (new)
- `src/LPP_message_gen.py` — added generate_lpp_request_assistance_data();
  rewrote the DL-TDoA provideAssistanceData branch to build from real PRS
  config instead of hardcoded values (modified)
- `src/LPP_handler.py` — handleLPP() now returns (response_bytes,
  lmf_instance) instead of sending directly; added ensure_session_for_lpp()
  and encode_nr_dl_prs_assistance_data() (modified)
- `src/lmf_server_api.py` — added a SUPL TCP listener running alongside the
  existing Flask HTTP interface, in the same process (modified)
- `src/lmf_instance.py`, `src/config.py`, `src/Dockerfile`,
  `docker-compose-lmf.yaml` — supporting changes for the above (modified)
