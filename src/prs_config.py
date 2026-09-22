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
