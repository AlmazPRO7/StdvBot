#!/bin/bash

# Переходим в папку скрипта
cd "$(dirname "$0")"

echo "🚀 Запуск ConstructionAI System (Bot + WebApp + Tunnel)..."

# 1. Убиваем старые процессы
pkill -f telegram_bot.py || true
pkill -f webapp_server.py || true
pkill -f cloudflared || true
rm -f tunnel.log tunnel_url.txt

# 2. Запускаем WebApp Server (Flask)
echo "🌐 Запускаем Web Dashboard (Port 5000)..."
nohup ./venv/bin/python3 src/webapp_server.py > web.log 2>&1 &
echo "   PID Web: $!"

# 3. Запускаем Cloudflare Tunnel
echo "🚇 Поднимаем туннель..."
# --url localhost:5000 пробрасывает локальный порт наружу
nohup ./cloudflared tunnel --url http://localhost:5000 > tunnel.log 2>&1 &
TUNNEL_PID=$!
echo "   PID Tunnel: $TUNNEL_PID"

# 4. Ждем получения URL (парсим логи)
echo "⏳ Ожидание публичного URL..."
attempt=0
while [ $attempt -le 20 ]; do
    if grep -q "trycloudflare.com" tunnel.log; then
        # Вытаскиваем URL через grep с regex
        url=$(grep -o 'https://[-a-zA-Z0-9]*\.trycloudflare\.com' tunnel.log | head -n 1)
        if [ ! -z "$url" ]; then
            echo "$url" > tunnel_url.txt
            echo "✅ Туннель активен: $url"
            break
        fi
    fi
    echo -n "."
    sleep 2
    attempt=$((attempt+1))
done

if [ ! -f tunnel_url.txt ]; then
    echo "❌ Не удалось получить URL туннеля. Проверьте tunnel.log"
fi

# 5. Запускаем Telegram Bot (он прочитает tunnel_url.txt)
echo "🤖 Запускаем Telegram Bot..."
nohup ./venv/bin/python3 telegram_bot.py > bot.log 2>&1 &
echo "   PID Bot: $!"

echo "✅ Система запущена!"
echo "Логи: tail -f bot.log web.log tunnel.log"
