[Unit]
Description=Stock Broker Onboarding FastAPI
After=network.target

[Service]
Type=simple
User=__APP_USER__
Group=__APP_GROUP__
WorkingDirectory=__API_ROOT__
EnvironmentFile=__ENV_FILE__
ExecStart=__VENV_BIN__/uvicorn app.main:app --host 127.0.0.1 --port __APP_PORT__ --workers 2
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
