#!/bin/bash
# Install rd-agent if the directory exists (optional for OSS builds)
set -e

if [ -d "rd-agent" ] && [ -f "rd-agent/setup.py" ]; then
    echo "rd-agent found, installing..."
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_RDAGENT=0.1.dev1 \
        python -m pip install --no-cache-dir --root-user-action=ignore ./rd-agent
    rm -rf rd-agent
    echo "rd-agent installed successfully."
else
    echo "rd-agent not found, skipping installation."
    echo "To enable Alpha Agent factor evolution, clone rd-agent into the project root."
fi
