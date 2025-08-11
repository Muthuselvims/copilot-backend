from app.utils.query_generator import generate_sql_with_openai
import os
from openai import OpenAI, OpenAIError
import json
import asyncio

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_sql_query(question, schema, system_prompt=None):
    default_prompt = (
        "You are a helpful assistant that generates optimized SQL Server queries. "
        "Based on the schema and user's question, return only a valid SQL SELECT statement. "
        "Do not add explanations or markdown. Use table and column names exactly as given in the schema."
    )
    return generate_sql_with_openai(question, schema, system_prompt or default_prompt)

async def  is_question_relevant_to_purpose(question: str, purpose: str) -> bool:
    prompt = (
        f"Check if the following user question aligns with the assistant's purpose.\n"
        f"Assistant Purpose: {purpose}\n"
        f"User Question: {question}\n"
        f"Respond only with 'Yes' or 'No'."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a relevance checker."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        answer = response.choices[0].message.content.strip().lower()
        return "yes" in answer
    except Exception as e:
        print(f"[Error checking relevance] {e}")
        return True  # Assume yes if API fails


import datetime

def serialize(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize(v) for v in obj]
    else:
        return obj
