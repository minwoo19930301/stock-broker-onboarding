#cloud-config
write_files:
  - path: /usr/local/bin/stock-broker-firstboot.sh
    permissions: "0755"
    owner: root:root
    content: |
      #!/bin/bash
      set -euxo pipefail

      APP_DIR="/opt/stock-broker-onboarding"
      TMP_BUNDLE="/tmp/stock-broker-onboarding.tar.gz"
      SERVICE_PATH="/etc/systemd/system/stock-broker-onboarding.service"

      mkdir -p /opt
      chown __APP_USER__:__APP_USER__ /opt

      curl -fsSL "__BUNDLE_URL__" -o "${TMP_BUNDLE}"

      rm -rf "${APP_DIR}"
      mkdir -p "${APP_DIR}"
      tar -xzf "${TMP_BUNDLE}" -C "${APP_DIR}"
      chown -R __APP_USER__:__APP_USER__ "${APP_DIR}"

      cat > "${SERVICE_PATH}" <<'EOF'
      [Unit]
      Description=Stock Broker Onboarding Static Server
      After=network-online.target
      Wants=network-online.target

      [Service]
      Type=simple
      WorkingDirectory=/opt/stock-broker-onboarding
      ExecStart=/usr/bin/python3 /opt/stock-broker-onboarding/server.py
      Restart=always
      RestartSec=2

      [Install]
      WantedBy=multi-user.target
      EOF

      systemctl daemon-reload
      systemctl enable stock-broker-onboarding.service
      systemctl restart stock-broker-onboarding.service

      if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
        firewall-cmd --permanent --add-service=http || true
        firewall-cmd --reload || true
      fi
runcmd:
  - [ bash, -lc, /usr/local/bin/stock-broker-firstboot.sh ]
