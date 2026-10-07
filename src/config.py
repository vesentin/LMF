# IP and PORT of the LMF within the docker network
LMF_IP = '0.0.0.0'
LMF_API_PORT = "4333"
#The LMF's real, reachable IP address, used to identify the server
#in SlpSessionID (ULP-Components.SlpSessionID).
#Needs to match the IP in 'docker-compose-lmf.yaml'
LMF_PUBLIC_IP = "192.168.70.140"

#LMF_IP = "lmf_net.org"
#LMF_API_PORT = "4321"
LMF_PORT = 9090

### CORE NETOWRK USED ##
CN_Used= "OAI"
#CN_Used = "free5gc"

match CN_Used:
    case "OAI": # IP/PORT FOR OAI core network
        AMF_IP = "192.168.70.132"
        AMF_PORT = 8080
    case "free5gc":     # IP/PORT FOR free5gc
        AMF_IP = "10.100.200.50"
        AMF_PORT = 8000




# identifiuer of lmf network function
nfID = "97bfff10-1add-4a3f-b8d6-6b08a3718129"
# Seconds between attempts to subscribe to the AMF for non-UE N2 (NRPPa) messages,
# until the first subscription succeeds (the AMF may start after the LMF)
NON_UE_SUB_RETRY_S = 5

# Maximum age (seconds) of the TRP table before a new request re-queries the gNBs.
# Implementation choice (not defined by TS 38.455). 5 minutes is enough for static
# TRPs; kept configurable for future, more realistic scenarios (e.g. NTN, where a
# TRP on a moving satellite changes position continuously).
TRP_TABLE_MAX_AGE_S = 300

# the maximum age of the estimation in minutes
MaxAgeOfEstimation= 5 

# NRPPa transaction ID ranges. NRPPATransactionID is 0..32767 in TS 38.455, but the
# OAI gNB copies it into an 8-bit F1AP transaction ID (0..255, TS 38.473) without
# translation, so IDs above 255 are truncated and the response is lost (the gNB then
# crashes). Workaround: keep every NRPPa transaction ID within 0..255.
#   0..199      used by UE positioning sessions (LMF_COMPUTING_DB)
#   200..255    used by TRP table queries (trp_table.py)
TRP_TXN_MIN = 200
TRP_TXN_MAX = 255
# TRP information types requested from the gNBs (TRPInformationTypeItem names, TS 38.455).
# Only types supported by the OAI gNB: unsupported ones are answered with a TRP Information
# Failure. 'pRSConfig' requires a prs_config section in each gNB .conf.
TRP_INFO_TYPES = ['nrPCI', 'nG-RAN-CGI', 'arfcn', 'geoCoord', 'pRSConfig']
# How long to wait for all gNBs to answer a TRP query (seconds)
TRP_QUERY_TIMEOUT_S = 2.0

# information of the cell where the UE is connected
mcc = "001"
mnc = "01"
tac = "000001"

gNB_bitLength= 32
gNBValue = "00000E00"
trpID= 0


#Config information for the Location Alogorthms
# origin lat and lon are the coordinates of the origin of the cartesian system (0,0,0)
origin_lat = 0
origin_lon = 0
gNBPos= [{'x': 0,'y': 0},             
         {'x': 0,'y':300},
         {'x': 300,'y':0},
         {'x': 300,'y':300}]

import os
# List of gNB .conf file paths, one per TRP, index-matched to prs.conf's
# TRP indices (GNB_CONF_PATHS[0] corresponds to prs_config0, etc.).
# Used to read real PhysCellID/ARFCN/SCS directly from each gNB's own
# config, instead of duplicating these fields into prs.conf by hand.
GNB_CONF_DIR = os.environ.get('GNB_CONF_DIR', '/LMF/gnb_confs')

GNB_CONF_PATHS = [
    os.path.join(GNB_CONF_DIR, "gnb0.sa.band255.u0.25prb.rfsim.ntn-leo-RegenWithPRS.multiru.conf"),
    os.path.join(GNB_CONF_DIR, "gnb1.sa.band255.u0.25prb.rfsim.ntn-leo-RegenWithPRS.multiru.conf"),
    os.path.join(GNB_CONF_DIR, "gnb2.sa.band255.u0.25prb.rfsim.ntn-leo-RegenWithPRS.multiru.conf"),
]
