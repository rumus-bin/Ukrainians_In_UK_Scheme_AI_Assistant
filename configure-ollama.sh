#!/bin/bash
# Script to configure Ollama to listen on 0.0.0.0 for Docker containers

set -e

echo "🔧 Configuring Ollama to listen on all interfaces..."
echo ""

# Create systemd override directory
echo "Creating systemd override directory..."
sudo mkdir -p /etc/systemd/system/ollama.service.d/

# Create override file
echo "Creating override configuration..."
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null <<EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

echo "✅ Override file created at /etc/systemd/system/ollama.service.d/override.conf"
echo ""

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Restart Ollama
echo "Restarting Ollama service..."
sudo systemctl restart ollama

# Wait for service to start
echo "Waiting for Ollama to start..."
sleep 3

# Check status
echo ""
echo "📊 Ollama Service Status:"
sudo systemctl status ollama --no-pager | head -15

echo ""
echo "🔍 Testing connection..."
sleep 2

# Test local connection
echo "Testing localhost connection..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Localhost connection: OK"
else
    echo "❌ Localhost connection: FAILED"
fi

# Test network connection
echo "Testing 0.0.0.0 connection..."
if curl -s http://0.0.0.0:11434/api/tags > /dev/null; then
    echo "✅ Network connection: OK"
else
    echo "❌ Network connection: FAILED"
fi

echo ""
echo "✅ Ollama configuration complete!"
echo "Ollama is now listening on: 0.0.0.0:11434"
echo "Docker containers can now connect via: host.docker.internal:11434"
echo ""
echo "To verify from Docker:"
echo "  docker exec ukraine-bot-scraper curl -s http://host.docker.internal:11434/api/tags"