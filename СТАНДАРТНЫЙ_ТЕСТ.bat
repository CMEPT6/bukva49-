@echo off
cd /d "%~dp0"
py -3 llm_benchmark.py --model qwen3.5:9b --per-family 2 --output llm_result.json
pause
