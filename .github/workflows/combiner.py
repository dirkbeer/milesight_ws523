# combiner.py (updated)
from pathlib import Path
import argparse

def main():
    parser = argparse.ArgumentParser(description='Combine repository files')
    parser.add_argument('--repo', type=str, default='.', help='Repository root path')
    parser.add_argument('--output', type=str, default='combined_code.txt', help='Output file name')
    args = parser.parse_args()

    REPO_ROOT = Path(args.repo).resolve()
    EXCLUDE = {'.git', '__pycache__', 'venv', args.output}  # Added output file to exclude
    
    try:
        with open(args.output, 'w', encoding='utf-8') as outfile:
            for path in REPO_ROOT.glob('**/*'):
                if path.name == args.output:  # Skip self
                    continue
                
                if path.is_file() and not any(p in path.parts for p in EXCLUDE):
                    rel_path = path.relative_to(REPO_ROOT)
                    try:
                        content = path.read_text(encoding='utf-8')
                        outfile.write(f"#@||FILE:{rel_path}||@#\n")
                        outfile.write(content)
                        outfile.write("\n\n")
                    except UnicodeDecodeError:
                        print(f"Skipping binary file: {rel_path}")
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
