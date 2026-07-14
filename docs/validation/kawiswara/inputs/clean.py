import os
import sys


def process_file():
    # Check if the user provided a filename argument
    if len(sys.argv) < 2:
        print("Error: Please provide an input file.")
        print("Usage: python script.py <filename>")
        sys.exit(1)

    input_filename = sys.argv[1]

    # Extract the base filename and folder path to construct the output name
    # This ensures it handles paths correctly (e.g., 'folder/in.txt' -> 'folder/cleaned-in.txt')
    dir_name, file_name = os.path.split(input_filename)
    output_filename = os.path.join(dir_name, f"cleaned-{file_name}")

    seen = set()
    unique_words = []

    try:
        # Read and process the input file
        with open(input_filename, "r", encoding="utf-8") as infile:
            for line in infile:
                words = line.split()
                for word in words:
                    if word not in seen:
                        seen.add(word)
                        unique_words.append(word)

    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' could not be found.")
        sys.exit(1)

    # Write the unique words to the new output file
    with open(output_filename, "w", encoding="utf-8") as outfile:
        for word in unique_words:
            outfile.write(word + "\n")

    print(f"Success! Cleaned data saved to: {output_filename}")


if __name__ == "__main__":
    process_file()
