# LMF — SUPL Transport for NR DL-TDoA

## Setup notes

### PRS configuration file

`docker-compose-lmf.yaml` mounts a PRS configuration file into the container
at `/LMF/prs.conf`, read by the LMF to generate real NR-DL-PRS-AssistanceData-r16
content.

It uses EURECOM OAI ue prs config files (they should all be compatible), and they are
NOT included in this repository. Before running, set OAI_CONF_DIR to the
directory containing this file on your own machine, e.g.:

    export OAI_CONF_DIR=/path/to/ue_prs_config_file

It is also required to do the same for the gNB/gNBs config files as they are also mounted
into the container.

   export GNB_CONF_DIR=/path/to/gNBs_prs_config_files

Each TRP in the assistance data now carries its own real PLMN, NR cell
identity, and PhysCellID -- read from its own conf in GNB_CONF_DIR/
GNB_CONF_PATHS, rather than a shared placeholder. Previously every TRP
reported the same constant cell identity; this is fixed.

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
(`os.environ.get('GNB_CONF_DIR', '/LMF/gnb_confs')`) instead of hardcoded
paths, so the same list resolves correctly both inside the LMF container
(default) and from `client_supl.py` running on the host -- export
`GNB_CONF_DIR` to the host-side directory containing the same gNB conf
files before running the client.

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
- `src/config.py` — `GNB_CONF_PATHS` now built from a `GNB_CONF_DIR` base
  directory (env var, defaulting to the container path) instead of
  hardcoded paths, so it resolves correctly both inside the LMF container
  and from a host-side client (modified)
- `src/lmf_instance.py`, `src/config.py`, `src/Dockerfile`,
  `docker-compose-lmf.yaml` — supporting changes for the above (modified)
