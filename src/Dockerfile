from ubuntu:jammy

# Install python
RUN apt update
RUN apt upgrade -y
RUN apt install curl software-properties-common apt-transport-https gnupg2 lsb-release vim -y
RUN add-apt-repository ppa:deadsnakes/ppa -y
RUN apt update
RUN DEBIAN_FRONTEND=noninteractive TZ=Europe/Rome apt install python3.12 -y
RUN apt install python-is-python3
RUN ln -sf /usr/bin/python3.12 /usr/bin/python3

# Install pip
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12


# Install envoy
RUN apt update
RUN curl -fsSL https://apt.envoyproxy.io/signing.key | gpg --dearmor -o /usr/share/keyrings/envoy-keyring.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/envoy-keyring.gpg] https://apt.envoyproxy.io jammy main" | tee /etc/apt/sources.list.d/envoy.list
RUN apt update
RUN apt install -y envoy


COPY src/requirements.txt LMF/src/

RUN pip install --ignore-installed -r LMF/src/requirements.txt
RUN pip install --force-reinstall websocket-client


COPY ../envoy_proxy/envoy.yaml /etc/envoy/envoy.yaml


COPY LICENSE LMF/
# COPY src/config.py LMF/src/
COPY src/HandleLocation.py src/lmf_instance.py src/lmf_server_api.py src/LPP_handler.py src/LPP_message_gen.py LMF/src/
COPY src/custom_log.py src/NRPPa_handler.py src/NRPPa_message_gen.py src/positiong_algorithm.py src/requirements.txt LMF/src/
COPY src/start.sh LMF/


# RUN envoy -c /etc/envoy/envoy.yaml &

WORKDIR LMF

CMD [ "/bin/bash", "start.sh"]
