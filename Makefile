.PHONY: run dev help train-dpo

# Default target
help:
	@echo "Available commands:"
	@echo "  make run        - Run the FastAPI server using uvicorn"
	@echo "  make dev        - Run the server in reload mode (alias for run)"
	@echo "  make train-dpo  - Run the DPO training script"

# Run the FastAPI server
run:
	uv run uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Alias for run
dev: run

# Run the DPO training script
train-dpo:
	uv run python studentProfileDetails/dpo_trainer.py

run-server:
	ngrok http 8000