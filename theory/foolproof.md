## Concerns

1. Much of the accuracy/usefulness of an application is determined before querying the LLM (In other words, it is the key either appropriate products can be selected by the similarity of the descriptions and user query)
2. When no foolproof is considered, it would implicitly mitigate user's satisfaction.

## Countermeasures for Foolproof

a. Use similarity score to cut off inappropriate results from the vector search

b. Use supplemental prompts to LLM such as "If you don't know the answer, just say that you don't know, don't try to make up an answer." or "If you cannot find any great recommendation from the given inputs, ask the user for more inputs"

Reference:

https://python.langchain.com/docs/use_cases/question_answering/how_to/vector_db_qa

```
from langchain.prompts import PromptTemplate
prompt_template = """Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

{context}

Question: {question}
Answer in Italian:"""
PROMPT = PromptTemplate(
    template=prompt_template, input_variables=["context", "question"]
)
```

https://docs.datastax.com/en/astra-serverless/docs/vector-search/cql.html

```
SELECT description, similarity_cosine(item_vector, [0.1, 0.15, 0.3, 0.12, 0.05]) 
    FROM vsearch.products 
    ORDER BY item_vector ANN OF [0.1, 0.15, 0.3, 0.12, 0.05] 
    LIMIT 1;
```

https://docs.datastax.com/en/astra-serverless/docs/vector-search/quickstart.html

```
first_question = True
while True:
    if first_question:
        query_text = input("\nEnter your question (or type 'quit' to exit): ")
        first_question = False
    else:
        query_text = input("\nWhat's your next question (or type 'quit' to exit): ")

    if query_text.lower() == "quit":
        break

    print("QUESTION: \"%s\"" % query_text)
    answer = vectorIndex.query(query_text, llm=llm).strip()
    print("ANSWER: \"%s\"\n" % answer)

    print("DOCUMENTS BY RELEVANCE:")
    for doc, score in myCassandraVStore.similarity_search_with_score(query_text, k=4):
        print("  %0.4f \"%s ...\"" % (score, doc.page_content[:60]))
```
