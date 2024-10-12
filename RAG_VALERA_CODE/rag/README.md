# СНАЧАЛА УСТОНОВИ docling из коробки
cd docling
pip install -e .
cd ..

# Потом установи все зависимости
pip install -r rag/requirements.txt

# Потом, сначала prep_rag_data.py, потом rag_inference.py