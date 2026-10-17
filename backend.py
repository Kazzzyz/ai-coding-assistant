

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_classic.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
import subprocess
import tempfile
import sys


def api_llm():
    load_dotenv()

    api_key = os.getenv("API_KEY")

    llm = ChatOpenAI(
        api_key = api_key,
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/free",
        temperature=0.8

    )
    return llm



def user_query(query):

    system_prompt1 = SystemMessage("""
You are a strict programming intent classifier.

Your only task is to classify the user's request into exactly one of these categories:

GENERATE
Use this when the user wants code to be written, created, implemented, completed, fixed, modified, or generated.

EXPLAIN
Use this when the user wants existing code, an error, a function, a line of code, or programming behavior to be explained or analyzed.

OTHER
Use this when the request is not about programming or cannot be confidently classified as GENERATE or EXPLAIN.

Rules:
- Do not answer the user's request.
- Do not generate code.
- Do not explain your decision.
- Do not add punctuation.
- Do not add any extra text.
- Your entire response must be exactly one of:

GENERATE
EXPLAIN
OTHER
""")

    total=[system_prompt1,HumanMessage(content=query)]

    return api_llm().invoke(total).content


def llm_code_explaination(query):
    
    system_prompt2 = SystemMessage("""
You are a professional software developer and code generation assistant.

Your task is to solve the user's programming request using the retrieved context as supporting knowledge.

Requirements:
- Produce a complete and usable solution.
- Follow the user's requested programming language and framework when specified.
- Use the retrieved context when it is relevant, but adapt it to the user's exact request.
- Do not blindly copy irrelevant parts of the retrieved context.
- Use clear variable and function names.
- Follow appropriate programming best practices.
- Include useful comments where they improve understanding.
- Include appropriate input validation and error handling when relevant.
- Do not omit required implementation details or replace them with placeholders such as "your code here".
- Ensure the code is syntactically valid to the best of your ability.
- Put executable source code inside a Markdown code block with the correct language identifier.
- After the code, provide only a brief explanation when useful.
""")
    total2=[system_prompt2,HumanMessage(content=query)]
    classifier2=api_llm().invoke(total2).content
    return classifier2


def llm_classification(query):
    classification = user_query(query) 

    if classification == "GENERATE":

        relevance_result = llm_relevant_check(query)

        if relevance_result == "RELEVANT":
            return relevant(query), "GENERATE"

        elif relevance_result == "NOT_RELEVANT":
            return "NEED_USER_SOLUTION", "GENERATE"

    elif classification == "EXPLAIN":
        return llm_code_explaination(query), "EXPLAIN"

    elif classification == "OTHER":
        return "Topic is not Coding Related"


    
def Retrieve_from_chroma(query):
    embedding_model = HuggingFaceEmbeddings(model_name= "sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma(persist_directory="Chroma_database",embedding_function=embedding_model)
    results = vectordb.similarity_search(query,k=3)
    return results


def llm_relevant_check(query):
    temp = """
You are a strict retrieval relevance evaluator.

Your only task is to determine whether the retrieved context contains enough useful information to support answering the user's programming request.

Return RELEVANT when the retrieved context contains useful code, algorithms, logic, examples, concepts, or implementation details related to the user's request.

Return NOT_RELEVANT when the retrieved context is unrelated, only weakly related, or does not contain enough useful information to support the requested solution.

Rules:
- Judge only the relationship between the user's request and the retrieved context.
- Do not answer the user's request.
- Do not generate code.
- Do not explain your reasoning.
- Do not add punctuation.
- Do not add any extra text.
- Your entire response must be exactly one of:

RELEVANT
NOT_RELEVANT

## conext:
{context}

## Question : 
{Question}
"""

    temp = PromptTemplate.from_template(temp)
    query=query
    similar_docs = Retrieve_from_chroma(query)

    context = []
    for i in similar_docs:
        context.append(i.page_content)

    prompt = temp.format(context="\n".join(context), Question =query)

    response = api_llm().invoke(prompt).content 

    return response



def relevant(query):
    similar_docs = Retrieve_from_chroma(query)

    context = []
    for i in similar_docs:
        context.append(i.page_content)


    generation_prompt = f"""
You are a professional software developer and code generation assistant.

Your task is to generate a complete solution for the user's programming request using the retrieved context as supporting knowledge.

Requirements:
- Produce complete and usable source code.
- Follow the programming language and framework requested by the user.
- Use the retrieved context when it is relevant to the request.
- Adapt the retrieved information to the user's exact problem rather than blindly copying it.
- Use clear variable, function, and class names.
- Follow appropriate programming best practices.
- Include useful comments where they improve clarity.
- Include appropriate validation and error handling when relevant.
- Do not leave placeholders such as "implement here" or "your code here".
- Ensure the code is syntactically valid to the best of your ability.
- Put all executable source code inside a Markdown code block with the correct language identifier.
- After the code, provide only a short explanation when useful.


User request:
{query}

Retrieved context:
{"\n".join(context)}

Generate:
- Complete source code
- Useful comments
- Best practices
- Appropriate error handling
- A short explanation if useful

Return the code using Markdown code blocks.
"""

    response = api_llm().invoke(generation_prompt).content

    return response


def non_relevant(query,solution): 

    #Ask user for the solution and then embedd it in vector database
    embedding_model = HuggingFaceEmbeddings(model_name= "sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma(persist_directory="Chroma_database",embedding_function=embedding_model)
    text = f"""
Problem:
{query} 

Solution:
{solution}
"""
    new_doc= Document(
        page_content=text,
        metadata={
        "source": "user_suggestion",
        }
    )
    
    vectordb.add_documents([new_doc])

    return "Thank you for teaching me! I'll remember this for future interactions."



def execute_code(code):

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8"
    ) as file:
        file.write(code)
        filename = file.name

    try:
        result = subprocess.run(
            [sys.executable, filename],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Execution timed out."
        }

    finally:
        if os.path.exists(filename):
            os.remove(filename)



def extract_code(response):
    import re
    match = re.search(
        r"```python\s*(.*?)```",
        response,
        re.DOTALL
    )

    if match:
        return match.group(1).strip()

    return response