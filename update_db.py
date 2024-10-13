import sqlite3
import os
from typing import List

import sqlite_vec
from sqlite_vec import serialize_float32
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from RAG_VALERA_CODE.rag.anything_to_md import convert_file_to_markdown  # Imported from anything_to_markdown.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
SOURCE_DIR = "/Users/maximmashtaler/Projects/prog/hacks/CP/szfo2024/cp11-10/RAG_VALERA_CODE/rag/data"
OUTPUT_DIR = "/Users/maximmashtaler/Projects/prog/hacks/CP/szfo2024/cp11-10/RAG_VALERA_CODE/rag/converted_md"
DB_NAME = "rzd.sqlite3"
EMBEDDING_MODEL = 'deepvk/USER-bge-m3'


def create_chunks(data: str) -> List[dict]:
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on, strip_headers=False)
    md_header_splits = markdown_splitter.split_text(data)

    chunk_size = 2048
    chunk_overlap = 512
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    splits = text_splitter.split_documents(md_header_splits)
    
    # Assuming split_documents returns a list of Document objects with page_content and metadata
    return splits


def setup_database(db):
    try:
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        logging.info("SQLite extensions loaded successfully.")
    except sqlite3.OperationalError as e:
        logging.error(f"Error loading SQLite extensions: {e}")
        raise

    try:
        db.execute("""
        CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            meta_data_h TEXT,
            meta_data_source TEXT,
            file_path TEXT UNIQUE
        );
        """)

        db.execute("""
        CREATE TABLE IF NOT EXISTS chunks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            text TEXT,
            meta_data_h TEXT,
            meta_data_source TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        );
        """)
        db.commit()
        logging.info("Database tables ensured.")
    except sqlite3.Error as e:
        logging.error(f"Error setting up database tables: {e}")
        db.rollback()
        raise


def create_embeddings_table(db, embedding_size):
    try:
        db.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings USING vec0(
            id INTEGER PRIMARY KEY,
            embedding FLOAT[{embedding_size}]
        );
        """)
        db.commit()
        logging.info("Embeddings table created or already exists.")
    except sqlite3.Error as e:
        logging.error(f"Error creating embeddings table: {e}")
        db.rollback()
        raise


def save_chunks(db, chunks: List[str], meta_data: List[dict], model, document_id: int):
    try:
        chunk_embeddings = list(model.encode(chunks, normalize_embeddings=True))
        for chunk, embedding, meta in zip(chunks, chunk_embeddings, meta_data):
            cursor = db.execute(
                "INSERT INTO chunks(document_id, text, meta_data_h, meta_data_source) VALUES(?, ?, ?, ?)", 
                (document_id, chunk, meta.get("header", ""), meta.get("source", ""))
            )
            chunk_id = cursor.lastrowid
            db.execute(
                "INSERT INTO chunk_embeddings(id, embedding) VALUES (?, ?)",
                (chunk_id, serialize_float32(embedding)),
            )
        db.commit()
        logging.info(f"Saved {len(chunks)} chunks and their embeddings.")
    except Exception as e:
        logging.error(f"Error saving chunks: {e}")
        db.rollback()


def process_file(db, model, input_path, output_path):
    try:
        convert_file_to_markdown(input_path, output_path)
        logging.info(f"Converted {input_path} to markdown.")
    except Exception as e:
        logging.error(f"Error converting file {input_path} to markdown: {e}")
        return

    try:
        with open(output_path, "r", encoding='utf-8') as f:
            data = f.read()
        logging.info(f"Read markdown file {output_path}.")
    except Exception as e:
        logging.error(f"Error reading markdown file {output_path}: {e}")
        return

    splits = create_chunks(data)
    if not splits:
        logging.warning(f"No chunks created for {input_path}.")
        return

    # Insert document and get document_id
    meta_document = {
        "source": input_path,
        "description": "Full Document"
    }
    try:
        cursor = db.execute(
            "INSERT INTO documents(text, meta_data_h, meta_data_source, file_path) VALUES(?, ?, ?, ?)", 
            (data, meta_document.get("description", ""), meta_document.get("source", ""), input_path)
        )
        document_id = cursor.lastrowid
        db.commit()
        logging.info(f"Inserted document {input_path} with ID {document_id}.")
    except sqlite3.IntegrityError:
        logging.warning(f"File {input_path} is already processed.")
        db.rollback()
        return
    except Exception as e:
        logging.error(f"Error inserting document {input_path}: {e}")
        db.rollback()
        return

    # Prepare metadata for chunks
    try:
        chunks_text = [chunk.page_content for chunk in splits]
        chunks_meta = [{"source": input_path, "header": chunk.metadata.get("header", "Unknown")} for chunk in splits]
        logging.info(f"Prepared metadata for {len(chunks_text)} chunks.")
    except Exception as e:
        logging.error(f"Error preparing chunk metadata for {input_path}: {e}")
        return

    # Save chunks and their embeddings
    save_chunks(db, chunks_text, chunks_meta, model, document_id)


class NewFileHandler(FileSystemEventHandler):
    def __init__(self, db, model):
        super().__init__()
        self.db = db
        self.model = model

    def on_created(self, event):
        if not event.is_directory:
            input_path = event.src_path
            relative_path = os.path.relpath(os.path.dirname(input_path), SOURCE_DIR)
            output_path_dir = os.path.join(OUTPUT_DIR, relative_path)
            if not os.path.exists(output_path_dir):
                os.makedirs(output_path_dir)
                logging.info(f"Created directory {output_path_dir}.")
            output_file = os.path.splitext(os.path.basename(input_path))[0] + '.md'
            output_path = os.path.join(output_path_dir, output_file)
            logging.info(f"Processing new file: {input_path}")
            process_file(self.db, self.model, input_path, output_path)


def main():
    try:
        # Initialize SentenceTransformer model
        logging.info(f"Loading SentenceTransformer model '{EMBEDDING_MODEL}'...")
        model = SentenceTransformer(EMBEDDING_MODEL)
        logging.info("Model loaded successfully.")

        # Setup database
        db_path = os.path.abspath(DB_NAME)
        logging.info(f"Connecting to database at {db_path}...")
        db = sqlite3.connect(db_path, check_same_thread=False)
        setup_database(db)

        # Determine embedding size from the model
        sample_embedding = model.encode("Sample text", normalize_embeddings=True)
        if hasattr(sample_embedding, 'shape'):
            embedding_size = sample_embedding.shape[0]
        else:
            embedding_size = len(sample_embedding)
        logging.info(f"Embedding size determined as {embedding_size}.")

        # Create embeddings table if not exists
        create_embeddings_table(db, embedding_size)

        # Setup watchdog observer
        event_handler = NewFileHandler(db, model)
        observer = Observer()
        observer.schedule(event_handler, path=SOURCE_DIR, recursive=True)
        observer.start()
        logging.info("Monitoring started. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Stopping observer due to KeyboardInterrupt.")
            observer.stop()
        observer.join()

    except Exception as e:
        logging.error(f"An error occurred in main: {e}")
    finally:
        if 'db' in locals():
            db.close()
            logging.info("Database connection closed.")


if __name__ == "__main__":
    main()