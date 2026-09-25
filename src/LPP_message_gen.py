import custom_log as log
import config
import re
from prs_config import read_prs_config

# FUNCTIONS FOR GENERATING THE LPP MESSAGES USED BY THE LMF
# GENERATE LPP ABORT MESSAGE
def generate_lpp_abort(type):
    # Type = undefined
    Abort= ("c1", ( "abort", { "criticalExtensions": ( "c1", ("abort-r9", {'commonIEsAbort': {'abortCause': type}}))}))
    return Abort

# GENERATE LPP ERROR MESSAGE
def generate_lpp_error(type):
    Error= ("c1", ( "error", ("error-r9", {'commonIEsError': {'errorCause': type}} )))
    return Error

# GENERATE LPP REQUEST CAPABILITIES FROM THE METHODS
def generate_lpp_request_capabilities(methods):

    RequestCabailities= ("c1", ( "requestCapabilities", { "criticalExtensions": ( "c1", ("requestCapabilities-r9", {}))}))
    checkMethods=['a-gnss-RequestCapabilities','otdoa-RequestCapabilities','ecid-RequestCapabilities','epdu-RequestCapabilities','sensor-RequestCapabilities-r13', 'tbs-RequestCapabilities-r13','wlan-RequestCapabilities-r13','bt-RequestCapabilities-r13','nr-ECID-RequestCapabilities-r16','nr-Multi-RTT-RequestCapabilities-r16','nr-DL-AoD-RequestCapabilities-r16','nr-DL-TDOA-RequestCapabilities-r16','nr-UL-RequestCapabilities-r16']

    commonIE= {'commonIEsRequestCapabilities': {'lpp-message-segmentation-req-r14': (0,2)}}
    RequestCabailities[1][1]['criticalExtensions'][1][1].update(commonIE)
    for item in methods:
        if item in checkMethods:

            if item=='a-gnss-RequestCapabilities':
                new_dict ={item: {'gnss-SupportListReq': True,'assistanceDataSupportListReq':False,'locationVelocityTypesReq':False}}
            else:
                new_dict = {item : {}}
            RequestCabailities[1][1]['criticalExtensions'][1][1].update(new_dict)
        else:    
            log.logger_LPP.error(f"Error during the generating of the request capabilities message - {item}")
            return 'ERROR'
    return RequestCabailities

# GENERATE LPP PROVIDE ASSISTANCE DATA FROM THE METHOD USED
# For the moment the assistance data response is fixed and Multi-RTT and TDOA are supported
# TODO fix the response based on the method and the capabilities of the networks
def _prs_bandwidth(num_rb):
    if num_rb < 24 or num_rb > 272 or (num_rb - 24) % 4 != 0:
        raise ValueError(
            f"PRS NumRB {num_rb} is not representable by "
            "LPP dl-PRS-ResourceBandwidth-r16"
        )

    return (num_rb - 20) // 4

def _prs_comb_size(comb_size):
    return {
        2: 'n2',
        4: 'n4',
        6: 'n6',
        12: 'n12'
    }[comb_size]


def _prs_num_symbols(num_symbols):
    return {
        2: 'n2',
        4: 'n4',
        6: 'n6',
        12: 'n12'
    }[num_symbols]


def _prs_repetition(repetition):
    return {
        2: 'n2',
        4: 'n4',
        6: 'n6',
        8: 'n8',
        16: 'n16',
        32: 'n32'
    }.get(repetition)

def _prs_scs_name(scs):
    return {
        0: 'kHz15',
        1: 'kHz30',
        2: 'kHz60',
        3: 'kHz120'
    }[scs]

def _prs_time_gap(time_gap):
    return {
        1: 'n1',
        2: 'n2',
        4: 'n4',
        8: 'n8',
        16: 'n16',
        32: 'n32'
    }[time_gap]

#unused --------------------------------
def _prs_muting_repetition(repetition):
    return {
        1: 'n1',
        2: 'n2',
        4: 'n4',
        8: 'n8'
    }[repetition]
#---------------------------------------

def read_gnb_cell_info(path):
    """
    Extract PhysCellID, ARFCN (dl_absoluteFrequencyPointA), and SCS
    (dl_subcarrierSpacing) directly from a real OAI gNB .conf file --
    avoids duplicating these into the separate UE-facing prs.conf.
    Simple regex line-scan, not a full libconfig parser: these three
    keys appear as flat "key = value;" lines and are unique within the
    file, so a targeted scan is sufficient without needing to understand
    the file's full nested structure.
    """
    with open(path) as f:
        text = f.read()

    def find_int(key):
        m = re.search(rf"\b{key}\s*=\s*(-?\d+)", text)
        if not m:
            raise ValueError(f"{key} not found in {path}")
        return int(m.group(1))

    return {
        'PhysCellID': find_int('physCellId'),
        'ARFCN': find_int('dl_absoluteFrequencyPointA'),
        'SCS': find_int('dl_subcarrierSpacing'),
    }

def _effective_prs_bandwidth_rb(configured_num_rb):
    """
    dl-PRS-ResourceBandwidth-r16 can only represent PRB counts of the form
    24, 28, 32, ..., 272 (steps of 4 from 24). If the configured NumRB
    doesn't fall on this grid (e.g. 106, a valid PHY carrier size with no
    valid LPP encoding), round DOWN to the nearest valid value -- staying
    within the configured/real carrier rather than exceeding it.
    """
    if configured_num_rb < 24:
        raise ValueError(
            f"Configured NumRB {configured_num_rb} is below the minimum "
            "LPP-representable PRS bandwidth (24 PRBs)"
        )

    effective = configured_num_rb - ((configured_num_rb - 24) % 4)

    if effective != configured_num_rb:
        log.logger_LPP.warning(
            f"Configured NumRB {configured_num_rb} has no valid "
            f"dl-PRS-ResourceBandwidth-r16 encoding; using {effective} PRBs "
            f"instead (nearest valid value not exceeding the configured carrier)"
        )

    return effective

def _prs_comb_and_re_offset(comb_size, re_offset):
    """
    LPP combines CombSize and REOffset into one CHOICE.
    """
    return (
        f'n{comb_size}-r16',
        re_offset
    )


def _build_prs_resource(cfg, resource_id, phys_cell_id):
    return {
        'nr-DL-PRS-ResourceID-r16': resource_id,
        'dl-PRS-SequenceID-r16': cfg['NPRS_ID'][resource_id],
        'dl-PRS-CombSizeN-AndReOffset-r16':
            _prs_comb_and_re_offset(
                cfg['CombSize'],
                cfg['REOffset'][resource_id]
            ),
        'dl-PRS-ResourceSlotOffset-r16':
            cfg['PRSResourceOffset'][resource_id],
        'dl-PRS-ResourceSymbolOffset-r16':
            cfg['SymbolStart'][resource_id],

        #QLC info: mirrors OAI's own gNB-side create_qlc() (lpp_prs.c), which
        #QLCs each PRS resource with the cell's first active SSB. Both current tests (band-78, NTN)
        #use bitmap = 1, so ssb_index = 0 is correct for these deployments; would need to change
        #if a config ever activates a different SSB pattern.

        'dl-PRS-QCL-Info-r16': (
            'ssb-r16',
            {
                'pci-r16': phys_cell_id,
                'ssb-Index-r16': 0,
                'rs-Type-r16': 'typeD'
            }
        )
    }


def _prs_periodicity(period, offset, scs=0):
    if offset >= period:
        raise ValueError(
            f"PRS resource-set offset {offset} must be smaller than period {period}"
        )

    periods = {
        0: {4, 5, 8, 10, 16, 20, 32, 40, 64, 80, 160, 320, 640,
            1280, 2560, 5120, 10240},

        1: {8, 10, 16, 20, 32, 40, 64, 80, 128, 160, 320, 640,
            1280, 2560, 5120, 10240, 20480},

        2: {16, 20, 32, 40, 64, 80, 128, 160, 256, 320, 640,
            1280, 2560, 5120, 10240, 20480, 40960},

        3: {32, 40, 64, 80, 128, 160, 256, 320, 512, 640, 1280,
            2560, 5120, 10240, 20480, 40960},
    }

    scs_names = {
        0: 'scs15-r16',
        1: 'scs30-r16',
        2: 'scs60-r16',
        3: 'scs120-r16',
    }

    if scs not in periods:
        raise ValueError(f"Unsupported PRS SCS value: {scs}")

    if period not in periods[scs]:
        raise ValueError(
            f"PRS period {period} is invalid for SCS value {scs}"
        )

    return (scs_names[scs], (f'n{period}-r16', offset))

def _build_prs_resource_set(cfg, resource_set_id=4, scs=0, phys_cell_id=None):
    """
    Build one LPP NR-DL-PRS ResourceSet from one OAI PRS configuration.
    scs is not read from a config file yet, so must be changed manually
    """

    period = cfg['PRSResourceSetPeriod'][0]
    offset = cfg['PRSResourceSetPeriod'][1]

    resource_set = {
        'nr-DL-PRS-ResourceSetID-r16': resource_set_id,

        'dl-PRS-Periodicity-and-ResourceSetSlotOffset-r16':
            _prs_periodicity(period, offset, scs),

        'dl-PRS-NumSymbols-r16':
            _prs_num_symbols(cfg['NumPRSSymbols'][0]),

        'dl-PRS-ResourcePower-r16': 33,

        'dl-PRS-ResourceList-r16': [
            _build_prs_resource(cfg, i, phys_cell_id)
            for i in range(cfg['NumPRSResources'])
        ]
    }

    repetition = cfg['PRSResourceRepetition']
    if repetition != 1:
        resource_set['dl-PRS-ResourceRepetitionFactor-r16'] = \
            _prs_repetition(repetition)

    time_gap = cfg['PRSResourceTimeGap']
    if time_gap != 1:
        resource_set['dl-PRS-ResourceTimeGap-r16'] = \
            _prs_time_gap(time_gap)

    return resource_set

def generate_lpp_provide_assistance_data(method):

    match method:

        case 'nr-Multi-RTT-RequestAssistanceData-r16':

            prs_configs = read_prs_config()
            cfg = prs_configs[0]

            resource_set = _build_prs_resource_set(
                cfg,
                resource_set_id=4,
                scs=cell_info['SCS']
            )

            AssistanceDataRTT = {
                'nr-DL-PRS-AssistanceData-r16': {
                    'nr-DL-PRS-ReferenceInfo-r16': {
                        'dl-PRS-ID-r16': 11,
                        'nr-DL-PRS-ResourceID-List-r16': [3, 4]
                    },

                    'nr-DL-PRS-AssistanceDataList-r16': [
                        {
                            'nr-DL-PRS-PositioningFrequencyLayer-r16': {
                                'dl-PRS-SubcarrierSpacing-r16': 'kHz15',
                                'dl-PRS-ResourceBandwidth-r16': 21,
                                'dl-PRS-StartPRB-r16': 22,
                                'dl-PRS-PointA-r16': 444,
                                'dl-PRS-CombSizeN-r16': 'n2',
                                'dl-PRS-CyclicPrefix-r16': 'normal'
                            },

                            'nr-DL-PRS-AssistanceDataPerFreq-r16': [
                                {
                                    'dl-PRS-ID-r16': 44,

                                    'nr-PhysCellID-r16': 33,

                                    'nr-CellGlobalID-r16': {
                                        'mcc-r15': [
                                            int(config.mcc[0]),
                                            int(config.mcc[1]),
                                            int(config.mcc[2])
                                        ],
                                        'mnc-r15': [
                                            int(config.mnc[0]),
                                            int(config.mnc[1])
                                        ],
                                        'nr-cellidentity-r15': (5, 36)
                                    },

                                    'nr-ARFCN-r16': 445,

                                    'nr-DL-PRS-SFN0-Offset-r16': {
                                        'sfn-Offset-r16': 44,
                                        'integerSubframeOffset-r16': 5
                                    },

                                    'nr-DL-PRS-ExpectedRSTD-r16': 4,

                                    'nr-DL-PRS-ExpectedRSTD-Uncertainty-r16': 55,

                                    'nr-DL-PRS-Info-r16': {
                                        'nr-DL-PRS-ResourceSetList-r16': [
                                            resource_set
                                        ]
                                    },

                                    'prs-OnlyTP-r16': 'true'
                                }
                            ]
                        }
                    ],

                    'nr-SSB-Config-r16': [
                        {
                            'nr-PhysCellID-r16': 33,
                            'nr-ARFCN-r16': 445,
                            'ss-PBCH-BlockPower-r16': 44,
                            'halfFrameIndex-r16': 1,
                            'ssb-periodicity-r16': 'ms5',
                            'ssb-PositionsInBurst-r16': (
                                'mediumBitmap-r16',
                                (1, 8)
                            ),
                            'ssb-SubcarrierSpacing-r16': _prs_scs_name(cell_info['SCS']),
                            'sfn-SSB-Offset-r16': 2
                        }
                    ]
                },

                'nr-SelectedDL-PRS-IndexList-r16': [
                    {
                        'nr-SelectedDL-PRS-FrequencyLayerIndex-r16': 1,

                        'nr-SelectedDL-PRS-IndexListPerFreq-r16': [
                            {
                                'nr-SelectedTRP-Index-r16': 1,

                                'dl-SelectedPRS-ResourceSetIndexList-r16': [
                                    {
                                        'nr-DL-SelectedPRS-ResourceSetIndex-r16': 1,

                                        'dl-SelectedPRS-ResourceIndexList-r16': [
                                            {
                                                'nr-DL-SelectedPRS-ResourceIdIndex-r16': 1
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

            ResponseLPP_Message_body = (
                "c1",
                (
                    "provideAssistanceData",
                    {
                        "criticalExtensions": (
                            "c1",
                            (
                                "provideAssistanceData-r9",
                                {
                                    'nr-Multi-RTT-ProvideAssistanceData-r16':
                                        AssistanceDataRTT
                                }
                            )
                        )
                    }
                )
            )


        case "nr-DL-TDOA-RequestAssistanceData-r16":

            prs_configs = read_prs_config()

            assistance_data_per_freq = []

            for trp_index, cfg in prs_configs.items():
                cell_info = read_gnb_cell_info(config.GNB_CONF_PATHS[trp_index])
                resource_set = _build_prs_resource_set(
                    cfg,
                    resource_set_id=4,
                    scs=cell_info['SCS'],
                    phys_cell_id=cell_info['PhysCellID'] 
                )

                assistance_data_per_freq.append({
                    'dl-PRS-ID-r16': trp_index,
                    'nr-PhysCellID-r16': cell_info['PhysCellID'],

                    'nr-CellGlobalID-r16': {
                        'mcc-r15': [
                            int(config.mcc[0]),
                            int(config.mcc[1]),
                            int(config.mcc[2])
                        ],
                        'mnc-r15': [
                            int(config.mnc[0]),
                            int(config.mnc[1])
                        ],
                        'nr-cellidentity-r15': (5, 36)
                    },

                    'nr-ARFCN-r16': cell_info['ARFCN'],

                    'nr-DL-PRS-SFN0-Offset-r16': {
                        'sfn-Offset-r16': 0,
                        'integerSubframeOffset-r16': 0
                    },

                    'nr-DL-PRS-ExpectedRSTD-r16': 4,
                    'nr-DL-PRS-ExpectedRSTD-Uncertainty-r16': 55,

                    'nr-DL-PRS-Info-r16': {
                        'nr-DL-PRS-ResourceSetList-r16': [resource_set]
                    },

                    'prs-OnlyTP-r16': 'true'
                })

            first_cfg = next(iter(prs_configs.values()))
            EFFECTIVE_NUM_RB = _effective_prs_bandwidth_rb(first_cfg['NumRB'])
            AssistanceDataDLTDOA = {
                'nr-DL-PRS-AssistanceData-r16': {
                    'nr-DL-PRS-ReferenceInfo-r16': {
                        'dl-PRS-ID-r16': 0,
                        'nr-DL-PRS-ResourceID-List-r16': [0]
                    },

                    'nr-DL-PRS-AssistanceDataList-r16': [
                        {
                            'nr-DL-PRS-PositioningFrequencyLayer-r16': {
                                'dl-PRS-SubcarrierSpacing-r16': 'kHz15',  # TODO: same as scs above
                                'dl-PRS-ResourceBandwidth-r16':
                                    _prs_bandwidth(EFFECTIVE_NUM_RB),
                                'dl-PRS-StartPRB-r16': 0,
                                'dl-PRS-PointA-r16': cell_info['ARFCN'],
                                'dl-PRS-CombSizeN-r16':
                                    _prs_comb_size(first_cfg['CombSize']),
                                'dl-PRS-CyclicPrefix-r16': 'normal'
                            },
                            'nr-DL-PRS-AssistanceDataPerFreq-r16': assistance_data_per_freq
                        }
                    ],
                    'nr-SSB-Config-r16': [
                        {
                            'nr-PhysCellID-r16': cell_info['PhysCellID'],
                            'nr-ARFCN-r16': cell_info['ARFCN'],
                            'ss-PBCH-BlockPower-r16': -25,
                            'halfFrameIndex-r16': 1,
                            'ssb-periodicity-r16': 'ms20',
                            'ssb-PositionsInBurst-r16': (
                                'mediumBitmap-r16',
                                (1, 8)
                            ),
                            # NOTE: dl-PRS-SubcarrierSpacing-r16 is a frequency-layer-level field (set 
                            # once, not per-TRP), so this assumes all TRPs in prs.conf share the same
                            # SCS -- true for all scenarios tested so far, but not enforced.
                            'ssb-SubcarrierSpacing-r16': _prs_scs_name(cell_info['SCS']),
                            'sfn-SSB-Offset-r16': 0
                        }
                    ]
                },

                'nr-SelectedDL-PRS-IndexList-r16': [
                    {
                        'nr-SelectedDL-PRS-FrequencyLayerIndex-r16': 1,

                        'nr-SelectedDL-PRS-IndexListPerFreq-r16': [
                            {
                                'nr-SelectedTRP-Index-r16': trp_index + 1,

                                'dl-SelectedPRS-ResourceSetIndexList-r16': [
                                    {
                                        'nr-DL-SelectedPRS-ResourceSetIndex-r16': 1,

                                        'dl-SelectedPRS-ResourceIndexList-r16': [
                                            {
                                                'nr-DL-SelectedPRS-ResourceIdIndex-r16': 1
                                            }
                                        ]
                                    }
                                ]
                            }
                            for trp_index in prs_configs
                        ]
                    }
                ]
            }

            ResponseLPP_Message_body = (
                "c1",
                (
                    "provideAssistanceData",
                    {
                        "criticalExtensions": (
                            "c1",
                            (
                                "provideAssistanceData-r9",
                                {
                                    'nr-DL-TDOA-ProvideAssistanceData-r16':
                                        AssistanceDataDLTDOA
                                }
                            )
                        )
                    }
                )
            )

        case _:
            log.logger_LPP.error(f"Unsupported method in generate_lpp_provide_assistance_data: {method}")
            ResponseLPP_Message_body = generate_lpp_error("incorrectDataValue")

    return ResponseLPP_Message_body

# GENERATE LPP REQUEST ASSISTANCE DATA FROM THE METHOD USED
# Counterpart to generate_lpp_provide_assistance_data(): this is the UE/SUPL-client
# -> LMF direction (asking for assistance data), not the LMF -> UE response.
# Per RequestAssistanceData-r9-IEs, every field is OPTIONAL, so a minimal,
# spec-compliant request can omit almost everything and still be valid.
def generate_lpp_request_assistance_data(method, phys_cell_id=None):

    match method:

        case 'nr-DL-TDOA-RequestAssistanceData-r16':

            nr_dl_tdoa_request = {
                # Bits: dl-prs (bit 0), posCalc (bit 1). (3, 2) = both requested.
                'nr-AdType-r16': (3, 2)
            }

            if phys_cell_id is not None:
                nr_dl_tdoa_request['nr-PhysCellID-r16'] = phys_cell_id

            RequestIEs = {
                'nr-DL-TDOA-RequestAssistanceData-r16': nr_dl_tdoa_request
            }

            RequestLPP_Message_body = (
                "c1",
                (
                    "requestAssistanceData",
                    {
                        "criticalExtensions": (
                            "c1",
                            (
                                "requestAssistanceData-r9",
                                RequestIEs
                            )
                        )
                    }
                )
            )

        case _:

            log.logger_LocAlg.error(
                "INTERNAL ERROR Methods non valid "
            )

            RequestLPP_Message_body = generate_lpp_error(
                "incorrectDataValue"
            )

    return RequestLPP_Message_body

# GENERATE LPP REQUEST LOCATION INFORMATION BASED ON METHOD, MODE
def generate_lpp_request_location_request(method,mode,configuration):
    

    QoS= configuration['QoS']

    LocationIEs={}
    match mode:
        case 'UE-Based':
            LocationIEs.update({'commonIEsRequestLocationInformation': {'locationInformationType': 'locationEstimateRequired'},})
        case 'UE-Assisted':
            LocationIEs.update({'commonIEsRequestLocationInformation': {'locationInformationType': 'locationMeasurementsRequired',
                                                                        'triggeredReporting': {'cellChange': True, 'reportingDuration': 0},
                                                                        'segmentationInfo-r14': 'noMoreMessages',
                                                                        'qos': QoS,
                                                                        'environment': 'mixedArea',
                                                                        'messageSizeLimitNB-r14': {'measurementLimit-r14':100},
                                                                        'targetIntegrityRisk-r17': 12,
                                                                        'scheduledLocationTime-r17': {
                                                                            'networkTime-r17': ('nrTime-r17', {
                                                                                'nr-PhysCellID-r17'	:	500,
                                                                                'nr-ARFCN-r17'		:	632628,
                                                                                'nr-CellGlobalID-r17':	{
                                                                                    'mcc-r15': [int(config.mcc[0]), int(config.mcc[1]), int(config.mcc[2])],
                                                                                    'mnc-r15': [int(config.mnc[0]), int(config.mnc[1])],
                                                                                    'nr-cellidentity-r15': (5,36) 
                                                                                                          },
                                                                                'nr-SFN-r17'		:	1,
                                                                                'nr-Slot-r17': ('scs30-r17',1)})
                                                                                }
                                                                                }
                                })
        case 'Standalone':
            LocationIEs.update({'commonIEsRequestLocationInformation': {'locationInformationType': 'locationEstimateRequired',
                                                                        'qos': QoS,
                                                                        'segmentationInfo-r14': 'noMoreMessages',
                                                                        'locationCoordinateTypes': {
                                                                                'ellipsoidPoint': True,
                                                                                'ellipsoidPointWithUncertaintyCircle': True,
                                                                                'ellipsoidPointWithUncertaintyEllipse': True,
                                                                                'polygon': False,
                                                                                'ellipsoidPointWithAltitude': True,
                                                                                'ellipsoidPointWithAltitudeAndUncertaintyEllipsoid': True,
                                                                                'ellipsoidArc': False
                                                                        },
                                                                        "velocityTypes" : {
                                                                                'horizontalVelocity': True,
                                                                                'horizontalWithVerticalVelocity': True,
                                                                                'horizontalVelocityWithUncertainty': True,
                                                                                'horizontalWithVerticalVelocityAndUncertainty': True
                                                                        }
                                                                        }})

    match method:
        case 'a-gnss':
            Val={
                'gnss-Methods': {'gnss-ids': (1,16)}, # GPS requested
                'fineTimeAssistanceMeasReq' : False,
                'adrMeasReq': False,
                'multiFreqMeasReq': False,
                'assistanceAvailability':False }
            LocationIEs.update({'a-gnss-RequestLocationInformation': {'gnss-PositioningInstructions': Val}})
        case 'otdoa':
            LocationIEs.update({'otdoa-RequestLocationInformation': {'assistanceAvailability': False}}) 
        case 'ecid':
            LocationIEs.update({'ecid-RequestLocationInformation': {'requestedMeasurements': (1,4)}})
        case 'sensor':
            log.logger_LocAlg.error(f' NOT SUPPORTED {method} METHOD')
            ResponseLPP_Message_body= generate_lpp_error("incorrectDataValue")
        case 'tbs':
            log.logger_LocAlg.error(f' NOT SUPPORTED {method} METHOD')
            ResponseLPP_Message_body= generate_lpp_error("incorrectDataValue")
        case 'wlan':
            log.logger_LPP.error(f' NOT SUPPORTED {method} METHOD')
            ResponseLPP_Message_body= generate_lpp_error("incorrectDataValue")
        case 'bt':
            log.logger_LPP.error(f' NOT SUPPORTED {method} METHOD')
            ResponseLPP_Message_body= generate_lpp_error("incorrectDataValue")
        case 'nr-ECID':
            LocationIEs.update({'nr-ECID-RequestLocationInformation-r16': {'requestedMeasurements-r16': (1,8)}})
        case 'nr-Multi-RTT':
            LocationIEs.update({'nr-Multi-RTT-RequestLocationInformation-r16': {   
                                                        'nr-UE-RxTxTimeDiffMeasurementInfoRequest-r16': 'true',
                                                        'nr-RequestedMeasurements-r16': (1,8),
                                                        'nr-AssistanceAvailability-r16': True,
                                                        'nr-Multi-RTT-ReportConfig-r16':  {'maxDL-PRS-RxTxTimeDiffMeasPerTRP-r16': 1,'timingReportingGranularityFactor-r16':1}}})                                            
        case 'nr-DL-AoD':
            log.logger_LPP.error(f' NOT SUPPORTED {method} METHOD')
            ResponseLPP_Message_body= generate_lpp_error("incorrectDataValue")
        case 'nr-DL-TDOA':      
            LocationIEs.update({ 'nr-DL-TDOA-RequestLocationInformation-r16': {
                'nr-DL-PRS-RstdMeasurementInfoRequest-r16': 'true',
                'nr-RequestedMeasurements-r16': (0,8),
                'nr-AssistanceAvailability-r16': False
                    }
                    })
        case _:
            log.logger_LPP.error('INTERNAL ERROR Methods non valid ')
            ResponseLPP_Message_body= generate_lpp_error("incorrectDataValue")



    RequestLocationInformation= ("c1", ( "requestLocationInformation", { "criticalExtensions": ( "c1", ("requestLocationInformation-r9", LocationIEs  ))}))
    ResponseLPP_Message_body = RequestLocationInformation
    return ResponseLPP_Message_body    


# FUNCTION TO GENERATE THE WHOLE LPP MESSAGE FROM THE MAIN VALUE
def generate_LPP_MESSAGE(transaction_number, end_transaction, sequence_number, lpp_message_body=None):
    if lpp_message_body==None:
        lpp_msg = {
            "transactionID": {
                "initiator": "locationServer",
                "transactionNumber": transaction_number % 255 
            },
            'acknowledgement':{'ackRequested':True},
            "endTransaction": end_transaction,
            "sequenceNumber": sequence_number  % 255 
        }
    else:
        lpp_msg = {
            "transactionID": {
                "initiator": "locationServer",
                "transactionNumber": transaction_number % 255 
            },
            'acknowledgement':{'ackRequested':True},
            "endTransaction": end_transaction,
            "sequenceNumber": sequence_number  % 255 ,
            "lpp-MessageBody": lpp_message_body
        }
    return lpp_msg

# FUNCTION TO GENERATE THE WHOLE LPP MESSAGE FROM THE MAIN VALUE
def generate_LPP__with_ACK(transaction_number, end_transaction, sequence_number, resp_ACK, lpp_message_body=None):
    
    if lpp_message_body==None:
        lpp_msg = {
            "transactionID": {
                "initiator": "locationServer",
                "transactionNumber": transaction_number % 255 
            },
            'acknowledgement':{'ackRequested': False,'ackIndicator': resp_ACK},
            "endTransaction": end_transaction,
            "sequenceNumber": sequence_number  % 255 ,
        }
    else:
        lpp_msg = {
            "transactionID": {
                "initiator": "locationServer",
                "transactionNumber": transaction_number % 255 
            },
            'acknowledgement':{'ackRequested':True,'ackIndicator':resp_ACK},
            "endTransaction": end_transaction,
            "sequenceNumber": sequence_number  % 255 ,
            "lpp-MessageBody": lpp_message_body

        } 
    return lpp_msg

