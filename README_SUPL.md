# LMF — SUPL Transport for NR DL-TDoA

## Setup notes

### Configuration files

The LMF reads the gNB configuration files (one per TRP, in gNB index order) and the UE PRS
configuration file. Their locations are set with environment variables:

| Variable | Meaning | Default |
|---|---|---|
| `GNB_CONF_DIR` | directory with the gNB configuration files | required |
| `GNB_CONF_FILES` | comma-separated gNB file names, in gNB index order | the names in `src/config.py` |
| `OAI_CONF_DIR` | directory with the UE PRS configuration file (often the same as `GNB_CONF_DIR`) | required |
| `UE_PRS_CONF` | UE PRS configuration file name | the name in `docker-compose-lmf.yaml` |

`client_supl.py` runs on the host and needs the same variables.

Set these variables in each terminal that runs `docker compose` or the client:

    export GNB_CONF_DIR=/path/to/gnb/confs
    export OAI_CONF_DIR=/path/to/ue/conf

`generate_lpp_provide_assistance_data()` also accepts an optional serving
cell (`serving_gnb_conf`, a gNB conf path, or `serving_pci`, a PhysCellID),
which -- when given -- filters the response to the TRPs that are NOT the
serving one, instead of reporting every TRP in GNB_CONF_PATHS. `LPP_handler.py`
passes a UE-reported `nr-PhysCellID-r16` through as `serving_pci` when
present. `client_supl.py` reads the serving gNB's PhysCellID directly from
`GNB_CONF_PATHS[0]` (via `read_gnb_cell_info()`) and includes it as
`nr-PhysCellID-r16` in the request, so this path is exercised by a real
client rather than a manually-supplied parameter.

`GNB_CONF_PATHS` is now built from a `GNB_CONF_DIR` base directory
instead of hardcoded paths, so the same list resolves correctly both 
inside the LMF container (default) and from `client_supl.py` running 
on the host.

### Network configuration (src/config.py)

`AMF_IP` and `CN_Used` in `config.py` are set to match the EURECOM test
network and will likely need to be changed for a different environment.

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
  config instead of hardcoded values; read_gnb_cell_info() now also reads
  PLMN/NR cell identity/tracking area code (comment-stripped, so a
  commented-out line in the conf can't be misread); nr-CellGlobalID-r16 is
  now real per-TRP data instead of a shared constant; added
  neighbouring_gnb_indices() and neighbouring_gnb_indices_by_pci() (PCI
  first, falls back to PLMN+NCI on a PCI collision) and optional
  serving_gnb_conf/serving_pci parameters on
  generate_lpp_provide_assistance_data() to filter the response to
  neighbouring TRPs (modified)
- `src/LPP_handler.py` — handleLPP() now returns (response_bytes,
  lmf_instance) instead of sending directly; added ensure_session_for_lpp()
  and encode_nr_dl_prs_assistance_data(); the DL-TDoA request case now
  passes a UE-reported nr-PhysCellID-r16 through as serving_pci (modified)
- `src/lmf_server_api.py` — added a SUPL TCP listener running alongside the
  existing Flask HTTP interface, in the same process (modified)

