FROM python:3.14-bookworm

ARG GID=1002
ARG UID=1002

RUN addgroup --gid ${GID} "flakehunter" && \
    adduser --disabled-password --gecos "FlakeFighters User,,," \
    --home /home/flakehunter --ingroup flakehunter --uid ${UID} flakehunter

# Set working directory
WORKDIR /home/flakehunter


# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
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


USER ${GID}:${UID}

RUN mkdir outputs

# Clone the repo and set up config with dummy details
RUN git clone https://github.com/home-assistant/core.git; \
    git config --global user.email "you@example.com"; \
    git config --global user.name "Your Name"

# Install pytest and the flake-fighting plugin
RUN pip install --no-cache-dir uv

# Copy the scripts
COPY --chown=${GID}:${UID} setup.sh setup.sh
COPY --chown=${GID}:${UID} fix_dependencies.py fix_dependencies.py
COPY --chown=${GID}:${UID} test.sh test.sh
RUN chmod +x setup.sh test.sh
