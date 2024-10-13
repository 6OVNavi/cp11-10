import sqlite3
import os
import json
from typing import List

import sqlite_vec
from sqlite_vec import serialize_float32
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from docling.document_converter import DocumentConverter
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from anything_to_md import convert_file_to_markdown  # Imported from anything_to_markdown.py

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
        meta_data_source TEXT
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
            if len(list(meta.values())) < 2:
                continue
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
    except Exception:
        pass

def main():
    try:
        # Directory containing files to process
        input_dir = SOURCE_DIR
        output_dir = OUTPUT_DIR

        # Ensure the output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Initialize SentenceTransformer model
        model = SentenceTransformer(EMBEDDING_MODEL)

        # Setup database
        db_path = os.path.abspath(DB_NAME)
        db = sqlite3.connect(DB_NAME)
        setup_database(db)

        # Process each file in the input directory
        for root, _, files in os.walk(input_dir):
            for file in tqdm(files, desc="Processing files"):
                input_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, input_dir)
                output_path_dir = os.path.join(output_dir, relative_path)
                if not os.path.exists(output_path_dir):
                    os.makedirs(output_path_dir)

                output_file = os.path.splitext(file)[0] + '.md'
                output_path = os.path.join(output_path_dir, output_file)

                # Convert file to markdown
                try:
                    convert_file_to_markdown(input_path, output_path)
                except Exception:
                    continue

                # Read markdown file
                try:
                    with open(output_path, "r", encoding='utf-8') as f:
                        data = f.read()
                except Exception:
                    continue

                # Create chunks
                splits = create_chunks(data)

                # Create embeddings
                try:
                    embeddings = model.encode([chunk.page_content for chunk in splits], normalize_embeddings=True)
                except Exception:
                    continue

                # Create embeddings table if not exists
                if root == input_dir and file == files[0]:  # Assuming embedding size is consistent
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
                        "INSERT INTO documents(text, meta_data_h, meta_data_source) VALUES(?, ?, ?)", 
                        [data, *list(meta_document.values())]
                    )
                    document_id = cursor.lastrowid
                    db.commit()
                except Exception:
                    continue

                # Prepare metadata for chunks
                try:
                    chunks_text = [chunk.page_content for chunk in splits]
                    chunks_meta = [{"source": input_path, **chunk.metadata} for chunk in splits]
                except Exception:
                    continue

                # Save chunks and their embeddings
                save_chunks(db, chunks_text, chunks_meta, model, document_id)
                print('vse top4ik')

    except Exception:
        pass
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    main()