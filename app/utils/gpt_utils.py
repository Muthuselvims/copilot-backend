from app.utils.query_generator import generate_sql_with_openai

def generate_sql_query(question, schema, system_prompt=None):
    default_prompt = (
        "You are a helpful assistant that generates optimized SQL Server queries. "
        "Based on the schema and user's question, return only a valid SQL SELECT statement. "
        "Do not add explanations or markdown. Use table and column names exactly as given in the schema."
    )
    return generate_sql_with_openai(question, schema, system_prompt or default_prompt)
