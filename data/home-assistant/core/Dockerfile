FROM python:3.14-bookworm

RUN addgroup --gid 1002 "flakehunter" && \
    adduser --disabled-password --gecos "FlakeFighters User,,," \
    --home /home/flakehunter --ingroup flakehunter --uid 1002 flakehunter

# Set working directory
WORKDIR /home/flakehunter

# Install system dependencies required for Home Assistant core
RUN apt-get update && apt-get install -y \
    git \
    libudev-dev \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*


USER 1002:1002


# Clone the repo and set up config with dummy details
RUN git clone https://github.com/home-assistant/core.git; \
    git config --global user.email "you@example.com"; \
    git config --global user.name "Your Name"

# Install pytest and the flake-fighting plugin
RUN pip install --no-cache-dir uv pytest pytest-flakefighters

# Copy the entrypoint script
COPY --chown=1002:1002 entrypoint.sh entrypoint.sh
COPY --chown=1002:1002 setup.sh setup.sh
RUN chmod +x entrypoint.sh setup.sh
RUN mkdir outputs && chmod 777 outputs
ENV PATH="$PATH:/home/flakehunter/.local/bin"
