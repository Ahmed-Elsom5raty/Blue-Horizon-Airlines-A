# Unconstrained ReAct Agent

## Description

This implementation demonstrates an Unconstrained LLM-Powered ReAct agent for handling airline disruption cases.

The agent autonomously decides which tools to use, how many tools to call, and when to stop reasoning. There are no predefined workflows, schemas, or step limits.

## Model

- Provider: OpenRouter
- Model: openrouter/free

## Requirements

Install the required packages:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file and add your OpenRouter API key:

```text
OPENROUTER_API_KEY=your_api_key_here
```

## Run

```bash
python main.py
```

## Available Tools

- check_available_flights
- issue_meal_voucher
- offer_travel_credit
- notify_hotel
