#!/bin/bash
# Finance Insight Service - Start Script
# This starts both the backend API and frontend UI

set -e

echo "🚀 Starting Finance Insight Service..."
echo ""

# Start backend in background
echo "📊 Starting backend API server on port 5000..."
cd "$(dirname "$0")"
uv run finance_insight_api --host 0.0.0.0 --port 5000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
sleep 3
until curl -s http://localhost:5000/health > /dev/null 2>&1; do
    sleep 1
done
echo "✅ Backend is ready!"

# Start frontend
echo "🎨 Starting frontend UI on port 3000..."
cd src/ui
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✨ Finance Insight Service is running!"
echo ""
echo "   Backend API:  http://localhost:5000"
echo "   Frontend UI:  http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Handle shutdown
trap "echo ''; echo '🛑 Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for both processes
wait
