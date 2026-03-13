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
      PORTS_SCRIPT="/usr/local/bin/stock-broker-open-ports.sh"
      PORTS_SERVICE="/etc/systemd/system/stock-broker-open-ports.service"
      APP_USER="__APP_USER__"

      if ! id "${APP_USER}" >/dev/null 2>&1; then
        for candidate in ubuntu opc ec2-user; do
          if id "${candidate}" >/dev/null 2>&1; then
            APP_USER="${candidate}"
            break
          fi
        done
      fi

      mkdir -p /opt
      chown "${APP_USER}:${APP_USER}" /opt

      curl -fsSL "__BUNDLE_URL__" -o "${TMP_BUNDLE}"

      rm -rf "${APP_DIR}"
      mkdir -p "${APP_DIR}"
      tar -xzf "${TMP_BUNDLE}" -C "${APP_DIR}"
      chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

      cat > "${PORTS_SCRIPT}" <<'EOF'
      #!/bin/bash
      set -euo pipefail
      if command -v iptables >/dev/null 2>&1; then
        iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -I INPUT 4 -p tcp --dport 80 -j ACCEPT
        iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
      fi
      EOF
      chmod 0755 "${PORTS_SCRIPT}"

      cat > "${PORTS_SERVICE}" <<'EOF'
      [Unit]
      Description=Open HTTP/HTTPS ports for Stock Broker Onboarding
      After=network-online.target
      Wants=network-online.target

      [Service]
      Type=oneshot
      ExecStart=/usr/local/bin/stock-broker-open-ports.sh
      RemainAfterExit=yes

      [Install]
      WantedBy=multi-user.target
      EOF

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
      systemctl enable stock-broker-open-ports.service
      systemctl restart stock-broker-open-ports.service
      systemctl enable stock-broker-onboarding.service
      systemctl restart stock-broker-onboarding.service

      if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
        firewall-cmd --permanent --add-service=http || true
        firewall-cmd --reload || true
      fi
runcmd:
  - [ bash, -lc, /usr/local/bin/stock-broker-firstboot.sh ]
