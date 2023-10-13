import streamlit as st
import dotenv
import langchain
import json

from cassandra.cluster import Session
from cassandra.query import PreparedStatement

from langchain.agents.agent_toolkits import create_retriever_tool, create_conversational_retrieval_agent
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.callbacks import StreamlitCallbackHandler
from langchain.schema import BaseRetriever, Document, SystemMessage

#from langchain.cache import CassandraSemanticCache

from cassandra.cluster import Cluster, Session
from cassandra.auth import PlainTextAuthProvider

# Enable langchain debug mode
#langchain.debug = True

dotenv.load_dotenv(dotenv.find_dotenv())


class AstraProductRetriever(BaseRetriever):
    session: Session
    embedding: OpenAIEmbeddings
    lang: str = "Japanese"
    search_statement_en: PreparedStatement = None
    search_statement_ja: PreparedStatement = None

    class Config:
        arbitrary_types_allowed = True

    def get_relevant_documents(self, query):
        docs = []
        embeddingvector = self.embedding.embed_query(query)
        if self.lang == "Japanese":
            if self.search_statement_ja is None:
                self.search_statement_ja = self.session.prepare("""
                    SELECT
                        id,
                        similarity_cosine(sem_vec, ?) as similarity,
                        title,
                        author,
                        publisher,
                        price,
                        description
                    FROM app.book_openai
                    ORDER BY sem_vec ANN OF ?
                    LIMIT ?
                    """)
            query = self.search_statement_ja
        else:
            if self.search_statement_en is None:
                self.search_statement_en = self.session.prepare("""
                    SELECT
                        id,
                        similarity_cosine(sem_vec, ?) as similarity,
                        title,
                        author,
                        publisher,
                        price,
                        description
                    FROM app.book_openai_en
                    ORDER BY sem_vec ANN OF ?
                    LIMIT ?
                    """)
            query = self.search_statement_en
        results = self.session.execute(query, [embeddingvector, embeddingvector, 5])
        top_products = results._current_rows
        for r in top_products:
            if r.similarity > 0.91:
                docs.append(Document(
                    id=r.id,
                    page_content=r.title,
                    metadata={"product id": r.id,
                            "title": r.title,
                            "author": r.author,
                            "publisher": r.publisher,
                            "description": r.description,
                            "price": r.price
                            }
                ))

        return docs


def get_session(scb: str, secrets: str) -> Session:
    """
    Connect to Astra DB using secure connect bundle and credentials.

    Parameters
    ----------
    scb : str
        Path to secure connect bundle.
    secrets : str
        Path to credentials.
    """

    cloud_config = {
        'secure_connect_bundle': scb
    }

    with open(secrets) as f:
        secrets = json.load(f)

    CLIENT_ID = secrets["clientId"]
    CLIENT_SECRET = secrets["secret"]

    auth_provider = PlainTextAuthProvider(CLIENT_ID, CLIENT_SECRET)
    cluster = Cluster(cloud=cloud_config, auth_provider=auth_provider)
    return cluster.connect()


@st.cache_resource
def create_chatbot(lang: str):
    print(f"Creating chatbot for {lang}...")
    session = get_session(scb='./config/secure-connect-demo.zip',
                          secrets='./config/demo-token.json')
    llm = ChatOpenAI(temperature=0, streaming=True)
    embedding = OpenAIEmbeddings()

    #langchain.llm_cache = CassandraSemanticCache(session=session,
    #                                             keyspace="bookstore",
    #                                             embedding=embedding,
    #                                             table_name="cass_sem_cache")

    retriever = AstraProductRetriever(
        session=session, embedding=embedding, lang=lang)
    retriever_tool = create_retriever_tool(
        retriever, "books_retrevier", "Useful when searching for books from a book store. Prices are in YEN.")
    system_message = """
    You are a customer service of a book store and you are asked to pick books for a customer.
    You must try to find books related to given questions first.
    You must use the books_retreiver.
    You must not provide any information other than books that you get from books_retriever.
    You should behave as a bookstore clerk.
    """
    if lang == "Japanese":
        system_message = f"{system_message} All the responses should be in Japanese language."
    message = SystemMessage(content=system_message)
    agent_executor = create_conversational_retrieval_agent(
        llm=llm, tools=[retriever_tool], system_message=message, verbose=True)
    return agent_executor


if 'history' not in st.session_state:
    st.session_state['history'] = {
        "English": [],
        "Japanese" : []
    }

st.set_page_config(layout="wide")

#with st.sidebar:
#    lang = st.radio(
#        "Chat language",
#        ["English", "Japanese"],
#        captions=[".", "Experimental", "."])
lang = "Japanese"
chatbot = create_chatbot(lang)


# Display chat messages from history on app rerun
for (query, answer) in st.session_state['history'][lang]:
    with st.chat_message("User"):
        st.markdown(query)
    with st.chat_message("Bot"):
        st.markdown(answer)

prompt = st.chat_input(placeholder="Ask chatbot")
if prompt:
    # Display user message in chat message container
    with st.chat_message("User"):
        st.markdown(prompt)
    # Display assistant response in chat message container
    with st.chat_message("Bot"):
        st_callback = StreamlitCallbackHandler(st.container())
        #result = result = chatbot.invoke({
        result = chatbot.invoke({
            "input": prompt,
            "chat_history": st.session_state['history'][lang]
        }, config={"callbacks": [st_callback]})
        st.session_state['history'][lang].append((prompt, result["output"]))
        st.markdown(result["output"])
