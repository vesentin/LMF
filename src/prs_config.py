import re


PRS_CONFIG_PATH = "/LMF/prs.conf"


def parse_value(value):
    value = value.strip()

    # Remove trailing semicolon
    if value.endswith(";"):
        value = value[:-1].strip()

    # List: [20, 2]
    if value.startswith("[") and value.endswith("]"):
        content = value[1:-1].strip()
        if not content:
            return []
        return [parse_value(item) for item in content.split(",")]

    # Empty list: []
    if value == "[]":
        return []

    # Integer
    if re.fullmatch(r"-?\d+", value):
        return int(value)

    # Otherwise keep it as a string
    return value


def read_prs_config(path=PRS_CONFIG_PATH):
    with open(path, "r") as f:
        text = f.read()

    configs = {}

    # Find each prs_configN = ( { ... } );
    pattern = re.compile(
        r"prs_config(\d+)\s*=\s*\(\s*\{(.*?)\}\s*\);",
        re.DOTALL
    )

    for match in pattern.finditer(text):
        config_number = int(match.group(1))
        body = match.group(2)

        config = {}

        for line in body.splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            config[key.strip()] = parse_value(value)

        configs[config_number] = config

    return configs


# ---------------------------------------------------------------------
# Serving cell of a gNB, read from its own OAI .conf file (used by the SUPL
# client to report the cell it is camped on in SUPL START / SUPL POS INIT).
# ---------------------------------------------------------------------
import warnings


def _strip_conf_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'(?m)(^|\s)(#|//).*$', r'\1', text)


def _conf_int(text, key, path, default=None):
    m = re.search(rf'\b{key}\s*=\s*(0[xX][0-9a-fA-F]+|\d+)[lL]?\s*[;,]', text)
    if not m:
        if default is None:
            raise ValueError(f"{key} not found in {path}")
        warnings.warn(f"{key} not found in {path}; using {default}")
        return default
    s = m.group(1)
    return int(s, 16) if s.lower().startswith('0x') else int(s)


def read_gnb_serving_cell(path):
    """
    Reads the identity of a gNB's cell from its OAI .conf file. The keys of the
    returned dict are the arguments of supl_message.build_nr_cell_information().

    arfcn_nr is the SSB frequency (absoluteFrequencySSB), NOT Point A.
    nr_cellid is optional in some confs (e.g. the band-78 one): it then defaults
    to 0 with a warning. Comments (#, //, /* */) are ignored.
    """
    with open(path) as f:
        text = _strip_conf_comments(f.read())

    m = re.search(r'\bplmn_list\s*=', text)
    if not m:
        raise ValueError(f"plmn_list not found in {path}")
    chunk = text[m.end():m.end() + 600]
    mcc = re.search(r'\bmcc\s*=\s*(\d+)', chunk)
    mnc = re.search(r'\bmnc\s*=\s*(\d+)', chunk)
    mnc_len = re.search(r'\bmnc_length\s*=\s*(\d+)', chunk)
    if not (mcc and mnc):
        raise ValueError(f"mcc/mnc not found in plmn_list of {path}")

    return {
        'phys_cell_id': _conf_int(text, 'physCellId', path),
        'arfcn_nr': _conf_int(text, 'absoluteFrequencySSB', path),
        'mcc': mcc.group(1).zfill(3),
        'mnc': mnc.group(1).zfill(int(mnc_len.group(1)) if mnc_len else 2),
        'nr_cell_identity': _conf_int(text, 'nr_cellid', path, default=0),
        'tracking_area_code': _conf_int(text, 'tracking_area_code', path),
    }
