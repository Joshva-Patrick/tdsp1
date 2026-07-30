import sys
import io
import json
import os
import traceback
import pandas as pd
import numpy as np
import requests
from openai import OpenAI

# Initialize the OpenAI SDK client configured for xAI (Grok)
XAI_API_KEY = os.getenv("XAI_API_KEY")

client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1"
)

# Supported Grok models: "grok-beta", "grok-2-1212", "grok-3", "grok-3-mini"
# Change this line:
GROK_MODEL = os.getenv("GROK_MODEL_NAME", "grok-4.5")

SYSTEM_PROMPT = """You are an expert Data Analyst LLM Agent.
When given a user query:
1. Analyze if dataset fetching or mathematical execution is needed.
2. Formulate and execute Python code using your code interpreter tool to fetch data or process calculations accurately.
3. Determine the EXACT requested shape of the answer specified in the user's prompt.
4. Output your response strictly as a JSON object matching the requested schema without any markdown formatting wrappers.
"""

def execute_python_code(code: str) -> str:
    """Executes python code safely and captures stdout."""
    output_buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = output_buffer
    
    local_vars = {"pd": pd, "np": np, "requests": requests}
    try:
        exec(code, local_vars)
        sys.stdout = old_stdout
        return output_buffer.getvalue()
    except Exception as e:
        sys.stdout = old_stdout
        return f"Execution Error: {str(e)}\n{traceback.format_exc()}"

def run_agent_task(chat_history: list, logger_callback) -> dict:
    """Runs the Grok LLM agent tool loop to answer the data analysis query."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history

    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_python_code",
                "description": "Execute Python code to download datasets (pandas/requests), clean, filter, aggregate, and calculate answers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Executable Python code"}
                    },
                    "required": ["code"]
                }
            }
        }
    ]

    for attempt in range(5):  # Max 5 reasoning loops
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        msg = response.choices[0].message
        logger_callback({"event": "llm_thought", "content": msg.content, "tool_calls": str(msg.tool_calls)})

        if not msg.tool_calls:
            content = msg.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
                
            try:
                return json.loads(content)
            except Exception:
                return {"answer": content}

        # Crucial Fix: Add the model's message object to context
        messages.append(msg)

        for tool_call in msg.tool_calls:
            if tool_call.function.name == "execute_python_code":
                args = json.loads(tool_call.function.arguments)
                result = execute_python_code(args["code"])
                
                logger_callback({
                    "event": "tool_execution",
                    "code": args["code"],
                    "output": result
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

    return {"answer": "Execution limit exceeded without conclusive output."}
