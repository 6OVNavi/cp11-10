import sqlite3
import os
from typing import List

import sqlite_vec
from sqlite_vec import serialize_float32
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from anything_to_md import convert_file_to_markdown  # Imported from anything_to_markdown.py

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

# Constants
SOURCE_DIR = "data/"
OUTPUT_DIR = "converted_md/"
DB_NAME = "rzd.sqlite3"
EMBEDDING_MODEL = 'deepvk/USER-bge-m3'


def create_chunks(data: str) -> List[str]:
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
    return splits


def setup_database(db):
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)

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


def create_embeddings_table(db, embedding_size):
    db.execute(f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS chunk_embeddings USING vec0(
        id INTEGER PRIMARY KEY,
        embedding FLOAT[{embedding_size}]
    );
    """)
    db.commit()


def save_chunks(db, chunks: List[str], meta_data: List[dict], model, document_id: int):
    try:
        chunk_embeddings = list(model.encode(chunks, normalize_embeddings=True))
        for chunk, embedding, meta in zip(chunks, chunk_embeddings, meta_data):
            result = db.execute(
                "INSERT INTO chunks(document_id, text, meta_data_h, meta_data_source) VALUES(?, ?, ?, ?)", 
                [document_id, chunk, *list(meta.values())]
            )
            chunk_id = result.lastrowid
            db.execute(
                "INSERT INTO chunk_embeddings(id, embedding) VALUES (?, ?)",
                [chunk_id, serialize_float32(embedding)],
            )
        db.commit()
    except Exception as e:
        print(f"Error saving chunks: {e}")
        db.rollback()


def process_file(db, model, input_path, output_path):
    try:
        convert_file_to_markdown(input_path, output_path)
    except Exception as e:
        print(f"Error converting file {input_path} to markdown: {e}")
        return

    try:
        with open(output_path, "r", encoding='utf-8') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading markdown file {output_path}: {e}")
        return

    splits = create_chunks(data)

    try:
        embeddings = model.encode([chunk.page_content for chunk in splits], normalize_embeddings=True)
    except Exception as e:
        print(f"Error creating embeddings for {input_path}: {e}")
        return

    # Create embeddings table if not exists
    if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunk_embeddings';").fetchone():
        if len(embeddings) > 0 and hasattr(embeddings[0], 'shape'):
            embedding_size = embeddings[0].shape[0]
        else:
            embedding_size = len(embeddings[0])
        create_embeddings_table(db, embedding_size)

    # Insert document and get document_id
    meta_document = {
        "source": input_path,
        "description": "Full Document"
    }
    try:
        cursor = db.execute(
            "INSERT INTO documents(text, meta_data_h, meta_data_source, file_path) VALUES(?, ?, ?, ?)", 
            [data, *list(meta_document.values()), input_path]
        )
        document_id = cursor.lastrowid
        db.commit()
    except sqlite3.IntegrityError:
        print(f"File {input_path} is already processed.")
        db.rollback()
        return
    except Exception as e:
        print(f"Error inserting document {input_path}: {e}")
        db.rollback()
        return

    # Prepare metadata for chunks
    try:
        chunks_text = [chunk.page_content for chunk in splits]
        chunks_meta = [{"source": input_path, **chunk.metadata} for chunk in splits]
    except Exception as e:
        print(f"Error preparing chunk metadata for {input_path}: {e}")
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
            output_file = os.path.splitext(os.path.basename(input_path))[0] + '.md'
            output_path = os.path.join(output_path_dir, output_file)
            process_file(self.db, self.model, input_path, output_path)


def main():
    try:
        # Initialize SentenceTransformer model
        model = SentenceTransformer(EMBEDDING_MODEL)

        # Setup database
        db_path = os.path.abspath(DB_NAME)
        db = sqlite3.connect(DB_NAME)
        setup_database(db)

        # Setup watchdog observer
        event_handler = NewFileHandler(db, model)
        observer = Observer()
        observer.schedule(event_handler, path=SOURCE_DIR, recursive=True)
        observer.start()
        print("Monitoring started. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'db' in locals():
            db.close()


if __name__ == "__main__":
    main()