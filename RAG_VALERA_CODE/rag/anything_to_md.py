# Convert anything to markdown

import os
import subprocess
import argparse
from docling.document_converter import DocumentConverter

converter = DocumentConverter()



def convert_pdf_to_markdown(source: str, output: str):
    global converter
    result = converter.convert_single(source)
    data = result.render_as_markdown()
    with open(output, "w") as f:
        f.write(data)


def convert_file_to_markdown(input_file, output_file):
    """
    Converts a given file to Markdown using Pandoc, excluding PDFs.

    Args:
        input_file (str): The path to the input file.
        output_file (str): The path where the Markdown file will be saved.
    """
    if input_file.lower().endswith('.pdf'):
        convert_pdf_to_markdown(input_file, output_file)
    else:
        # Determine the input format based on the file extension
        _, file_extension = os.path.splitext(input_file)
        input_format = file_extension[1:] if file_extension else 'txt'

        subprocess.run([
            'pandoc',
            '-f', input_format,
            '-t', 'pdf',
            '--pdf-engine', 'weasyprint',
            input_file,
            '-o', input_file + '.pdf'
        ], check=True)
        convert_pdf_to_markdown(input_file + '.pdf', output_file)

    print(f"Converted '{input_file}' to '{output_file}'")

def process_directory(input_dir, output_dir):
    """
    Processes all files in the input directory, converting them to Markdown.

    Args:
        input_dir (str): The directory containing input files.
        output_dir (str): The directory where Markdown files will be saved.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for root, _, files in os.walk(input_dir):
        for file in files:
            input_path = os.path.join(root, file)
            relative_path = os.path.relpath(root, input_dir)
            output_path_dir = os.path.join(output_dir, relative_path)
            if not os.path.exists(output_path_dir):
                os.makedirs(output_path_dir)
            output_file = os.path.splitext(file)[0] + '.md'
            output_path = os.path.join(output_path_dir, output_file)
            convert_file_to_markdown(input_path, output_path)

def main():
    parser = argparse.ArgumentParser(description="Convert files to Markdown using Pandoc, excluding PDFs.")
    parser.add_argument('input', help="Path to the input file or directory.")
    parser.add_argument('output', help="Path to the output Markdown file or directory.")
    args = parser.parse_args()


    if os.path.isfile(args.input):
        if args.input.lower().endswith('.pdf'):
            print("PDF conversion is handled separately. Skipping this file.")
            return
        convert_file_to_markdown(args.input, args.output)
    elif os.path.isdir(args.input):
        process_directory(args.input, args.output)
    else:
        print("Invalid input path. Please provide a valid file or directory.")

if __name__ == "__main__":
    main()