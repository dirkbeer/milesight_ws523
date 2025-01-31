from pathlib import Path
import argparse

def main():
    parser = argparse.ArgumentParser(description='Split combined file')
    parser.add_argument('--input', type=str, required=True, help='Input combined file')
    parser.add_argument('--output', type=str, default='restored', help='Output directory')
    args = parser.parse_args()

    OUTPUT_DIR = Path(args.output)
    current_file = None
    content = []
    
    try:
        with open(args.input, 'r', encoding='utf-8') as infile:
            for line in infile:
                if line.startswith("#@||FILE:"):
                    if current_file is not None and content:
                        write_file(current_file, content, OUTPUT_DIR)
                    current_file = line.split("||@#")[0].split("FILE:")[1].strip()
                    content = []
                else:
                    content.append(line)
            
            if current_file and content:
                write_file(current_file, content, OUTPUT_DIR)
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

def write_file(rel_path, content, output_dir):
    full_path = output_dir / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove extra empty lines at end of file
    cleaned = ''.join(content).rstrip('\n') + '\n'
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    print(f"Restored: {rel_path}")

if __name__ == "__main__":
    main()
