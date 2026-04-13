#!/usr/bin/env bash
# RAG 문서 인덱싱 트리거. 마스터 또는 kubectl 가능한 곳에서 실행.
set -euo pipefail
kubectl -n weather wait --for=condition=ready pod -l app=weather-api --timeout=120s
kubectl -n weather wait --for=condition=ready pod -l app=qdrant --timeout=120s
kubectl -n weather port-forward svc/weather-api 8000:80 &
PF_PID=$!
trap "kill $PF_PID" EXIT
sleep 3
curl -X POST http://localhost:8000/rag/ingest
echo
